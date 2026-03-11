import { io } from 'socket.io-client';
import type { Socket } from 'socket.io-client';
import crypto from 'node:crypto';
import { DaemonClientError } from '../errors/DaemonClientError';
import { DaemonSocketEvent, REVERSE_CHANNEL } from '../contracts/index';
import type { SocketOptions } from './types';
import type { TeamClusterDaemonMessage, TeamClusterDaemonSocketResponsePayload } from '../contracts/reverseChannel';
import type { ReverseChannelBridge } from '../reverse-channel/ReverseChannelBridge';

interface CommandResponseEnvelope<T> {
    status: string;
    data: T;
};

interface ControlSocketManagerCallbacks {
    onConnected: () => void;
    onDisconnected: (reason: string) => void;
    onError: (err: DaemonClientError) => void;
};

/**
 * Manages the socket.io-client control connection to the Volt server.
 *
 * Responsibilities:
 * - Establish and maintain the `socket.io` connection.
 * - Emit `team-cluster-daemon:register` on each (re)connect.
 * - Forward inbound `team-cluster-daemon:message` events to the bridge.
 * - Implement outbound `sendCommand` with request/response semantics and timeout.
 * - Emit arbitrary outbound messages via `emit`.
 */
export class ControlSocketManager {
    private socket: Socket | null = null;
    private registered = false;
    private activeSocketId = 0;
    private bridge: ReverseChannelBridge | null = null;

    constructor(
        private readonly controlSocketUrl: string,
        private readonly socketOptions: SocketOptions,
        private readonly callbacks: ControlSocketManagerCallbacks
    ) {}

    /**
     * Establishes the socket.io connection and waits for the server to
     * acknowledge the `team-cluster-daemon:registered` event.
     *
     * @param teamClusterId - Cluster identifier sent in the register payload.
     * @param daemonPassword - Current (possibly just-rotated) daemon password.
     * @throws {DaemonClientError} with code `SOCKET_CONNECTION_FAILED` on initial connect error.
     */
    connect(teamClusterId: string, daemonPassword: string): Promise<void> {
        this.registered = false;
        this.socket?.removeAllListeners();
        this.socket?.close();

        const socketId = ++this.activeSocketId;

        const socket = io(this.controlSocketUrl, {
            autoConnect: true,
            forceNew: true,
            reconnection: this.socketOptions.reconnect !== false,
            reconnectionAttempts: this.socketOptions.maxReconnectAttempts ?? Infinity,
            reconnectionDelay: this.socketOptions.reconnectBaseDelayMs ?? 500,
            reconnectionDelayMax: this.socketOptions.reconnectMaxDelayMs ?? 30_000,
            randomizationFactor: this.socketOptions.randomizationFactor ?? 0.3
        });

        this.socket = socket;

        return new Promise<void>((resolve, reject) => {
            let resolved = false;

            const finishOnce = (fn: () => void) => {
                if (resolved) {
                    return;
                }
                resolved = true;
                fn();
            };

            socket.on('connect', () => {
                socket.emit(DaemonSocketEvent.TeamClusterDaemonRegister, {
                    teamClusterId,
                    daemonPassword
                });
            });

            socket.on(DaemonSocketEvent.TeamClusterDaemonRegistered, () => {
                if (this.activeSocketId !== socketId) {
                    return;
                }

                this.registered = true;
                this.callbacks.onConnected();
                finishOnce(resolve);
            });

            socket.on('disconnect', (reason: string) => {
                if (this.activeSocketId !== socketId) {
                    return;
                }

                this.registered = false;
                this.bridge?.cleanup();
                this.callbacks.onDisconnected(reason);
            });

            socket.on('connect_error', (error: Error) => {
                if (this.activeSocketId !== socketId) {
                    return;
                }

                const clientError = DaemonClientError.socketConnectionFailed(
                    `Control socket connection error: ${error.message}`,
                    error
                );
                this.callbacks.onError(clientError);
                finishOnce(() => reject(clientError));
            });

            if (this.bridge) {
                this.bridge.bindToSocket(socket, socketId, () => this.activeSocketId);
            }
        });
    }

    /**
     * Registers the reverse-channel bridge so it is automatically rebound
     * whenever a new socket is created (initial connect and reconnections).
     */
    setBridge(bridge: ReverseChannelBridge): void {
        this.bridge = bridge;
    }

    /** Gracefully disconnects the socket and clears internal state. */
    disconnect(): void {
        this.registered = false;
        this.socket?.removeAllListeners();
        this.socket?.close();
        this.socket = null;
    }

    /**
     * Sends a command to the server and waits for the corresponding response.
     *
     * Uses a UUID-keyed request/response pattern over the
     * `team-cluster-daemon:message` event with an optional timeout.
     *
     * @param command - Command name, e.g. `"runtime.heartbeat"`.
     * @param payload - Arbitrary command payload.
     * @param timeoutMs - Override the per-call timeout in milliseconds.
     * @returns The `data.data` field from the server response envelope.
     * @throws {DaemonClientError} `SOCKET_NOT_READY` when not connected.
     * @throws {DaemonClientError} `COMMAND_TIMEOUT` when no response arrives in time.
     * @throws {DaemonClientError} `COMMAND_REJECTED` when the server returns `ok: false`.
     */
    sendCommand<T>(command: string, payload?: object, timeoutMs?: number): Promise<T | undefined> {
        if (!this.socket || !this.registered) {
            return Promise.reject(DaemonClientError.socketNotReady());
        }

        const requestId = crypto.randomUUID();
        const effectiveTimeout = timeoutMs ?? 30_000;

        return new Promise<T | undefined>((resolve, reject) => {
            const timeout = setTimeout(() => {
                this.socket?.off(DaemonSocketEvent.TeamClusterDaemonMessage, onMessage);
                reject(DaemonClientError.commandTimeout(command));
            }, effectiveTimeout);

            const onMessage = (message: unknown) => {
                if (
                    typeof message !== 'object' ||
                    message === null ||
                    Array.isArray(message)
                ) {
                    return;
                }

                const typed = message as TeamClusterDaemonSocketResponsePayload<CommandResponseEnvelope<T>>;

                if (typed.type !== 'response' || typed.requestId !== requestId) {
                    return;
                }

                clearTimeout(timeout);
                this.socket?.off(DaemonSocketEvent.TeamClusterDaemonMessage, onMessage);

                if (!typed.ok) {
                    reject(DaemonClientError.commandRejected(command, typed.message));
                    return;
                }

                resolve(typed.data?.data);
            };

            this.socket?.on(DaemonSocketEvent.TeamClusterDaemonMessage, onMessage);
            this.socket?.emit(DaemonSocketEvent.TeamClusterDaemonMessage, {
                type: 'command',
                requestId,
                command,
                responseType: REVERSE_CHANNEL.ResponseType.Json,
                payload
            });
        });
    }

    /**
     * Emits an arbitrary outbound message on the control socket without waiting
     * for a response. Used for fire-and-forget notifications such as exposure
     * snapshots and session data chunks.
     *
     * @throws {DaemonClientError} `EMIT_FAILED` when the socket is not connected.
     */
    emit(message: TeamClusterDaemonMessage): void {
        if (!this.socket) {
            throw DaemonClientError.emitFailed();
        }

        this.socket.emit(DaemonSocketEvent.TeamClusterDaemonMessage, message);
    }

    /** Returns whether the socket is connected and the register ACK was received. */
    isReady(): boolean {
        return this.registered;
    }
};
