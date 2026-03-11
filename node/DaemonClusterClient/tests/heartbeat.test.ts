/**
 * Unit tests for HeartbeatManager.
 */
import assert from 'node:assert/strict';
import { describe, it, beforeEach, afterEach } from 'node:test';
import { HeartbeatManager } from '../src/heartbeat/HeartbeatManager.ts';

describe('HeartbeatManager', () => {
    let sendHeartbeat: (payload: Record<string, unknown>) => Promise<void>;
    let onError: (error: unknown) => void;
    let sendCallCount: number;
    let errorCallCount: number;
    let lastPayload: Record<string, unknown> | null;
    let lastError: unknown;

    beforeEach(() => {
        sendCallCount = 0;
        errorCallCount = 0;
        lastPayload = null;
        lastError = null;

        sendHeartbeat = async (payload) => {
            sendCallCount++;
            lastPayload = payload;
        };

        onError = (error) => {
            errorCallCount++;
            lastError = error;
        };
    });

    it('fires immediately on start', async () => {
        const manager = new HeartbeatManager({ interval: 10_000 }, sendHeartbeat, onError);
        manager.start();

        await new Promise<void>((resolve) => setTimeout(resolve, 20));
        manager.stop();

        assert.equal(sendCallCount, 1);
    });

    it('does not fire after stop', async () => {
        const manager = new HeartbeatManager({ interval: 50 }, sendHeartbeat, onError);
        manager.start();
        manager.stop();

        await new Promise<void>((resolve) => setTimeout(resolve, 100));
        assert.equal(sendCallCount, 0);
    });

    it('uses payloadFactory result as payload', async () => {
        const manager = new HeartbeatManager(
            { interval: 10_000, payloadFactory: () => ({ foo: 'bar' }) },
            sendHeartbeat,
            onError
        );
        manager.start();
        await new Promise<void>((resolve) => setTimeout(resolve, 20));
        manager.stop();

        assert.deepEqual(lastPayload, { foo: 'bar' });
    });

    it('calls onError and continues loop when sendHeartbeat throws', async () => {
        let callCount = 0;
        const failingHeartbeat = async (_payload: Record<string, unknown>) => {
            callCount++;
            if (callCount === 1) {
                throw new Error('heartbeat failed');
            }
        };

        const manager = new HeartbeatManager({ interval: 30 }, failingHeartbeat, onError);
        manager.start();

        await new Promise<void>((resolve) => setTimeout(resolve, 100));
        manager.stop();

        assert.ok(errorCallCount >= 1, 'onError should have been called at least once');
        assert.ok(callCount >= 2, 'heartbeat should have been retried after failure');
    });

    it('calls onError when payloadFactory throws and skips send', async () => {
        const manager = new HeartbeatManager(
            {
                interval: 10_000,
                payloadFactory: () => { throw new Error('factory failure'); }
            },
            sendHeartbeat,
            onError
        );
        manager.start();
        await new Promise<void>((resolve) => setTimeout(resolve, 20));
        manager.stop();

        assert.equal(sendCallCount, 0);
        assert.equal(errorCallCount, 1);
        assert.ok(lastError instanceof Error);
    });

    it('start() is idempotent - calling twice does not double-fire', async () => {
        const manager = new HeartbeatManager({ interval: 10_000 }, sendHeartbeat, onError);
        manager.start();
        manager.start();

        await new Promise<void>((resolve) => setTimeout(resolve, 20));
        manager.stop();

        assert.equal(sendCallCount, 1);
    });
});
