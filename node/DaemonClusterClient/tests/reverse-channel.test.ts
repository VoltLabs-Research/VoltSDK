/**
 * Unit tests for ReverseChannelBridge.
 * Uses a mock socket that simulates the socket.io-client interface.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { ReverseChannelBridge } from '../src/reverse-channel/ReverseChannelBridge.ts';
import { DaemonClientErrorCode } from '../src/errors/error-codes.ts';
import { DaemonSocketEvent } from '../src/contracts/events.ts';
import type { TeamClusterDaemonMessage } from '../src/contracts/reverseChannel.ts';

interface MockSocketEmit {
    event: string;
    payload: unknown;
};

const createMockSocket = () => {
    const listeners = new Map<string, Array<(msg: unknown) => void>>();
    const emitted: MockSocketEmit[] = [];

    return {
        on(event: string, listener: (msg: unknown) => void) {
            const list = listeners.get(event) ?? [];
            list.push(listener);
            listeners.set(event, list);
        },
        emit(event: string, payload: unknown) {
            emitted.push({ event, payload });
        },
        trigger(event: string, payload: unknown) {
            for (const listener of listeners.get(event) ?? []) {
                listener(payload);
            }
        },
        emitted
    };
};

describe('ReverseChannelBridge', () => {
    it('dispatches command to registered handler and replies', async () => {
        const bridge = new ReverseChannelBridge();
        const socket = createMockSocket();

        bridge.registerHandler('test.command', {
            handle: async (_payload, _ctx) => ({ data: { result: 42 } })
        });

        bridge.bindToSocket(socket as never, 1, () => 1);

        socket.trigger(DaemonSocketEvent.TeamClusterDaemonMessage, {
            type: 'command',
            requestId: 'req-1',
            command: 'test.command',
            payload: { foo: 'bar' }
        } satisfies TeamClusterDaemonMessage);

        // Allow async handler to complete
        await new Promise<void>((resolve) => setTimeout(resolve, 10));

        const reply = socket.emitted.find(
            (e) =>
                e.event === DaemonSocketEvent.TeamClusterDaemonMessage &&
                (e.payload as Record<string, unknown>).requestId === 'req-1'
        );

        assert.ok(reply, 'expected a reply to be emitted');
        const payload = reply.payload as Record<string, unknown>;
        assert.equal(payload.ok, true);
        assert.equal(payload.status, 200);
    });

    it('replies with 404 for unknown command', async () => {
        const bridge = new ReverseChannelBridge();
        const socket = createMockSocket();

        bridge.bindToSocket(socket as never, 1, () => 1);

        socket.trigger(DaemonSocketEvent.TeamClusterDaemonMessage, {
            type: 'command',
            requestId: 'req-2',
            command: 'nonexistent.command',
            payload: {}
        } satisfies TeamClusterDaemonMessage);

        await new Promise<void>((resolve) => setTimeout(resolve, 10));

        const reply = socket.emitted[0].payload as Record<string, unknown>;
        assert.equal(reply.ok, false);
        assert.equal(reply.status, 404);
    });

    it('replies with 500 and calls onError when handler throws', async () => {
        const bridge = new ReverseChannelBridge();
        const socket = createMockSocket();

        let capturedError: unknown = null;
        bridge.onError((err) => { capturedError = err; });

        bridge.registerHandler('fail.command', {
            handle: () => { throw new Error('boom'); }
        });

        bridge.bindToSocket(socket as never, 1, () => 1);

        socket.trigger(DaemonSocketEvent.TeamClusterDaemonMessage, {
            type: 'command',
            requestId: 'req-3',
            command: 'fail.command',
            payload: {}
        } satisfies TeamClusterDaemonMessage);

        await new Promise<void>((resolve) => setTimeout(resolve, 10));

        const reply = socket.emitted[0].payload as Record<string, unknown>;
        assert.equal(reply.ok, false);
        assert.equal(reply.status, 500);
        assert.ok(capturedError !== null, 'onError should have been called');
        assert.equal((capturedError as { code: string }).code, DaemonClientErrorCode.HandlerError);
    });

    it('forwards non-command messages to onMessage listeners', async () => {
        const bridge = new ReverseChannelBridge();
        const socket = createMockSocket();

        const received: TeamClusterDaemonMessage[] = [];
        bridge.onMessage((msg) => received.push(msg as TeamClusterDaemonMessage));

        bridge.bindToSocket(socket as never, 1, () => 1);

        socket.trigger(DaemonSocketEvent.TeamClusterDaemonMessage, {
            type: 'session-input',
            sessionId: 'sess-1',
            chunkBase64: 'aGVsbG8=',
            isBinary: false
        } satisfies TeamClusterDaemonMessage);

        await new Promise<void>((resolve) => setTimeout(resolve, 10));

        assert.equal(received.length, 1);
        assert.equal(received[0].type, 'session-input');
    });

    it('ignores stale socket events after reconnect', async () => {
        const bridge = new ReverseChannelBridge();
        const socket = createMockSocket();
        let activeSocketId = 1;

        bridge.bindToSocket(socket as never, 1, () => activeSocketId);

        // Simulate reconnect: active socket id bumped to 2
        activeSocketId = 2;

        bridge.registerHandler('stale.command', {
            handle: async () => ({ data: { ok: true } })
        });

        socket.trigger(DaemonSocketEvent.TeamClusterDaemonMessage, {
            type: 'command',
            requestId: 'req-stale',
            command: 'stale.command',
            payload: {}
        } satisfies TeamClusterDaemonMessage);

        await new Promise<void>((resolve) => setTimeout(resolve, 10));

        assert.equal(socket.emitted.length, 0, 'stale socket events should be ignored');
    });

    it('unregisterHandler removes handler — unknown command reply is 404', async () => {
        const bridge = new ReverseChannelBridge();
        const socket = createMockSocket();

        bridge.registerHandler('removable.cmd', {
            handle: async () => ({ data: {} })
        });
        bridge.unregisterHandler('removable.cmd');
        bridge.bindToSocket(socket as never, 1, () => 1);

        socket.trigger(DaemonSocketEvent.TeamClusterDaemonMessage, {
            type: 'command',
            requestId: 'req-rm',
            command: 'removable.cmd',
            payload: {}
        } satisfies TeamClusterDaemonMessage);

        await new Promise<void>((resolve) => setTimeout(resolve, 10));

        const reply = socket.emitted[0].payload as Record<string, unknown>;
        assert.equal(reply.status, 404);
    });
});
