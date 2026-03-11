/**
 * Unit tests for DaemonClientError.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { DaemonClientError } from '../src/errors/DaemonClientError.ts';
import { DaemonClientErrorCode } from '../src/errors/error-codes.ts';

describe('DaemonClientError', () => {
    it('is an instance of Error', () => {
        const err = DaemonClientError.commandTimeout('runtime.heartbeat');
        assert.ok(err instanceof Error);
        assert.ok(err instanceof DaemonClientError);
    });

    it('has the correct name', () => {
        const err = DaemonClientError.socketNotReady();
        assert.equal(err.name, 'DaemonClientError');
    });

    it('enrollmentFailed sets correct code', () => {
        const err = DaemonClientError.enrollmentFailed('bad token');
        assert.equal(err.code, DaemonClientErrorCode.EnrollmentFailed);
    });

    it('commandTimeout includes command name in message', () => {
        const err = DaemonClientError.commandTimeout('runtime.lifecycle');
        assert.equal(err.code, DaemonClientErrorCode.CommandTimeout);
        assert.ok(err.message.includes('runtime.lifecycle'));
    });

    it('commandRejected uses server message when provided', () => {
        const err = DaemonClientError.commandRejected('jobs.retry', 'not authorized');
        assert.equal(err.code, DaemonClientErrorCode.CommandRejected);
        assert.equal(err.message, 'not authorized');
    });

    it('commandRejected falls back to default message', () => {
        const err = DaemonClientError.commandRejected('jobs.retry');
        assert.ok(err.message.includes('jobs.retry'));
    });

    it('handlerError carries cause', () => {
        const cause = new Error('original');
        const err = DaemonClientError.handlerError('container.start', cause);
        assert.equal(err.code, DaemonClientErrorCode.HandlerError);
        assert.equal(err.cause, cause);
    });
});
