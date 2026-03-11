import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';
import AxiosHttpClient from '../src/core/AxiosHttpClient';
import ApiError from '../src/errors/ApiError';

describe('AxiosHttpClient – FormData Content-Type stripping', () => {
    it('removes the default application/json Content-Type when body is FormData', async () => {
        const client = new AxiosHttpClient({ baseUrl: 'http://test.local' });

        /**
         * Reach into the internal axios instance to attach the mock adapter.
         * AxiosHttpClient exposes no public handle, so we access it through
         * the private field via bracket notation for test purposes only.
         */
        const axiosInstance = (client as unknown as { api: ReturnType<typeof axios.create> }).api;
        const mock = new MockAdapter(axiosInstance);

        let capturedContentType: string | undefined;

        mock.onPost('/upload').reply((config) => {
            capturedContentType = config.headers?.['Content-Type'] as string | undefined;
            return [200, { status: 'success', data: {} }];
        });

        const form = new FormData();
        form.append('file', new Blob(['hello']), 'hello.txt');

        await client.request({ method: 'POST', url: '/upload', body: form });

        assert.ok(
            capturedContentType !== 'application/json',
            `Content-Type must not be application/json for FormData — got: ${capturedContentType}`
        );

        mock.restore();
    });

    it('keeps Content-Type: application/json for plain object bodies', async () => {
        const client = new AxiosHttpClient({ baseUrl: 'http://test.local' });
        const axiosInstance = (client as unknown as { api: ReturnType<typeof axios.create> }).api;
        const mock = new MockAdapter(axiosInstance);

        let capturedContentType: string | undefined;

        mock.onPost('/data').reply((config) => {
            capturedContentType = config.headers?.['Content-Type'] as string | undefined;
            return [200, { status: 'success', data: {} }];
        });

        await client.request({ method: 'POST', url: '/data', body: { name: 'test' } });

        assert.ok(
            capturedContentType?.includes('application/json'),
            `Content-Type should be application/json, got: ${capturedContentType}`
        );

        mock.restore();
    });
});

describe('AxiosHttpClient – error normalization', () => {
    it('wraps a 404 response as ApiError with Http::404 code', async () => {
        const client = new AxiosHttpClient({ baseUrl: 'http://test.local' });
        const axiosInstance = (client as unknown as { api: ReturnType<typeof axios.create> }).api;
        const mock = new MockAdapter(axiosInstance);

        // Empty body — no server code, so fallback code Http::404 is used
        mock.onGet('/missing').reply(404, {});

        await assert.rejects(
            () => client.request({ method: 'GET', url: '/missing' }),
            (err: unknown) => {
                assert.ok(err instanceof ApiError, 'should be ApiError');
                assert.strictEqual((err as ApiError).code, 'Http::404');
                assert.strictEqual((err as ApiError).status, 404);
                return true;
            }
        );

        mock.restore();
    });

    it('prefers the server-provided code over the HTTP fallback code', async () => {
        const client = new AxiosHttpClient({ baseUrl: 'http://test.local' });
        const axiosInstance = (client as unknown as { api: ReturnType<typeof axios.create> }).api;
        const mock = new MockAdapter(axiosInstance);

        mock.onGet('/rbac').reply(403, { code: 'Team::AccessDenied' });

        await assert.rejects(
            () => client.request({ method: 'GET', url: '/rbac' }),
            (err: unknown) => {
                assert.ok(err instanceof ApiError);
                assert.strictEqual((err as ApiError).code, 'Team::AccessDenied');
                return true;
            }
        );

        mock.restore();
    });

    it('wraps network failures as Network::ConnectionError', async () => {
        const client = new AxiosHttpClient({ baseUrl: 'http://test.local' });
        const axiosInstance = (client as unknown as { api: ReturnType<typeof axios.create> }).api;
        const mock = new MockAdapter(axiosInstance);

        mock.onGet('/unreachable').networkError();

        await assert.rejects(
            () => client.request({ method: 'GET', url: '/unreachable' }),
            (err: unknown) => {
                assert.ok(err instanceof ApiError);
                assert.strictEqual((err as ApiError).code, 'Network::ConnectionError');
                return true;
            }
        );

        mock.restore();
    });
});
