import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import VoltClient from '../src/core/VoltClient';
import type { HttpClient, HttpRequest } from '../src/core/HttpClient';

/** Minimal synchronous HttpClient stub that records calls */
const makeStubClient = (handler: (req: HttpRequest) => unknown): HttpClient => ({
    request<T>(req: HttpRequest): Promise<T> {
        return Promise.resolve(handler(req) as T);
    }
});

describe('VoltClient – GET in-flight deduplication', () => {
    it('issues only one underlying request for simultaneous identical GETs', async () => {
        let callCount = 0;
        const stub = makeStubClient((req) => {
            callCount++;
            return { status: 'success', data: { id: req.url } };
        });

        const client = new VoltClient(stub, '/items');

        const [a, b, c] = await Promise.all([
            client.get('/'),
            client.get('/'),
            client.get('/')
        ]);

        assert.strictEqual(callCount, 1, 'underlying HTTP should be called exactly once');
        assert.deepStrictEqual(a, b);
        assert.deepStrictEqual(b, c);
    });

    it('issues a new request after the first one settles', async () => {
        let callCount = 0;
        const stub = makeStubClient(() => {
            callCount++;
            return { status: 'success', data: {} };
        });

        const client = new VoltClient(stub, '/items');

        await client.get('/');
        await client.get('/');

        assert.strictEqual(callCount, 2, 'sequential requests should each hit the server');
    });

    it('does NOT deduplicate requests with different query params', async () => {
        let callCount = 0;
        const stub = makeStubClient(() => {
            callCount++;
            return { status: 'success', data: {} };
        });

        const client = new VoltClient(stub, '/items');

        await Promise.all([
            client.get('/', { page: 1 }),
            client.get('/', { page: 2 })
        ]);

        assert.strictEqual(callCount, 2);
    });
});

describe('VoltClient – RBAC teamId injection', () => {
    it('injects /:teamId into the URL when useRBAC is true', async () => {
        const capturedUrls: string[] = [];
        const stub = makeStubClient((req) => {
            capturedUrls.push(req.url);
            return { status: 'success', data: {} };
        });

        const client = new VoltClient(stub, '/container', {
            useRBAC: true,
            getTeamId: () => 'team-42'
        });

        await client.get('/');

        assert.strictEqual(capturedUrls.length, 1);
        assert.ok(
            capturedUrls[0].includes('/team-42'),
            `URL should contain /team-42, got: ${capturedUrls[0]}`
        );
    });

    it('throws when useRBAC is true but getTeamId returns null', async () => {
        const stub = makeStubClient(() => ({}));
        const client = new VoltClient(stub, '/container', {
            useRBAC: true,
            getTeamId: () => null
        });

        await assert.rejects(
            () => client.get('/'),
            (err: Error) => err.message.includes('missing teamId')
        );
    });

    it('does NOT inject teamId when useRBAC is false', async () => {
        const capturedUrls: string[] = [];
        const stub = makeStubClient((req) => {
            capturedUrls.push(req.url);
            return { status: 'success', data: {} };
        });

        const client = new VoltClient(stub, '/public', {
            useRBAC: false,
            getTeamId: () => 'team-42'
        });

        await client.get('/resource');

        assert.ok(
            !capturedUrls[0].includes('team-42'),
            `URL must not contain teamId when RBAC is disabled, got: ${capturedUrls[0]}`
        );
    });

    it('withTeam creates a new client that injects the given teamId', async () => {
        const capturedUrls: string[] = [];
        const stub = makeStubClient((req) => {
            capturedUrls.push(req.url);
            return { status: 'success', data: {} };
        });

        const base = new VoltClient(stub, '/ws');
        const scoped = base.withTeam('team-99');

        await scoped.get('/members');

        assert.ok(
            capturedUrls[0].includes('/team-99'),
            `withTeam URL must include teamId, got: ${capturedUrls[0]}`
        );
    });
});
