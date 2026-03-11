/**
 * Unit tests for EnrollmentClient.
 * Uses native Node.js fetch mock via globalThis override.
 */
import assert from 'node:assert/strict';
import { describe, it, beforeEach, mock } from 'node:test';
import { EnrollmentClient } from '../src/enrollment/EnrollmentClient.ts';
import { DaemonClientError } from '../src/errors/DaemonClientError.ts';
import { DaemonClientErrorCode } from '../src/errors/error-codes.ts';

const makeResponse = (
    body: unknown,
    status: number = 200
): Response => {
    return {
        ok: status >= 200 && status < 300,
        status,
        json: () => Promise.resolve(body)
    } as unknown as Response;
};

describe('EnrollmentClient', () => {
    let client: EnrollmentClient;
    let fetchMock: ReturnType<typeof mock.fn>;

    beforeEach(() => {
        client = new EnrollmentClient({ url: 'https://volt.test/api/team-clusters/abc/healthcheck' });
        fetchMock = mock.fn(() =>
            Promise.resolve(
                makeResponse({
                    data: {
                        daemonPassword: 'rotated-pw-xyz',
                        teamCluster: { _id: 'abc', status: 'connected' }
                    }
                })
            )
        );

        globalThis.fetch = fetchMock as unknown as typeof fetch;
    });

    it('returns rotated daemonPassword on success', async () => {
        const result = await client.enroll('enrollment-token-123', '1.0.0');
        assert.equal(result.daemonPassword, 'rotated-pw-xyz');
        assert.deepEqual(result.teamCluster, { _id: 'abc', status: 'connected' });
    });

    it('sends correct POST body', async () => {
        await client.enroll('tok-abc', '2.0.0');
        assert.equal(fetchMock.mock.calls.length, 1);
        const [url, init] = fetchMock.mock.calls[0].arguments as [string, RequestInit];
        assert.equal(url, 'https://volt.test/api/team-clusters/abc/healthcheck');
        assert.equal(init.method, 'POST');
        assert.deepEqual(
            JSON.parse(init.body as string),
            { enrollmentToken: 'tok-abc', installedVersion: '2.0.0' }
        );
    });

    it('throws DaemonClientError.EnrollmentFailed on non-2xx response', async () => {
        fetchMock = mock.fn(() =>
            Promise.resolve(makeResponse({ error: 'Unauthorized' }, 401))
        );
        globalThis.fetch = fetchMock as unknown as typeof fetch;

        await assert.rejects(
            () => client.enroll('bad-token'),
            (err: unknown) => {
                assert.ok(err instanceof DaemonClientError);
                assert.equal(err.code, DaemonClientErrorCode.EnrollmentFailed);
                return true;
            }
        );
    });

    it('throws DaemonClientError.EnrollmentFailed on network error', async () => {
        fetchMock = mock.fn(() => Promise.reject(new Error('ECONNREFUSED')));
        globalThis.fetch = fetchMock as unknown as typeof fetch;

        await assert.rejects(
            () => client.enroll('some-token'),
            (err: unknown) => {
                assert.ok(err instanceof DaemonClientError);
                assert.equal(err.code, DaemonClientErrorCode.EnrollmentFailed);
                return true;
            }
        );
    });

    it('throws DaemonClientError.EnrollmentFailed when response missing daemonPassword', async () => {
        fetchMock = mock.fn(() =>
            Promise.resolve(makeResponse({ data: { teamCluster: {} } }))
        );
        globalThis.fetch = fetchMock as unknown as typeof fetch;

        await assert.rejects(
            () => client.enroll('tok'),
            (err: unknown) => {
                assert.ok(err instanceof DaemonClientError);
                assert.equal(err.code, DaemonClientErrorCode.EnrollmentFailed);
                return true;
            }
        );
    });
});
