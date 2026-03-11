import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import ApiError from '../src/errors/ApiError';
import extractServerCode from '../src/errors/extract-server-code';
import { getHttpFallbackCode } from '../src/core/http-utils';

describe('error normalization', () => {
    it('maps 400 to Http::400', () => {
        assert.strictEqual(getHttpFallbackCode(400), 'Http::400');
    });

    it('maps 401 to Http::401', () => {
        assert.strictEqual(getHttpFallbackCode(401), 'Http::401');
    });

    it('maps 403 to Http::403', () => {
        assert.strictEqual(getHttpFallbackCode(403), 'Http::403');
    });

    it('maps 404 to Http::404', () => {
        assert.strictEqual(getHttpFallbackCode(404), 'Http::404');
    });

    it('maps 409 to Http::409', () => {
        assert.strictEqual(getHttpFallbackCode(409), 'Http::409');
    });

    it('maps 429 to Http::429', () => {
        assert.strictEqual(getHttpFallbackCode(429), 'Http::429');
    });

    it('maps 500 to Http::500', () => {
        assert.strictEqual(getHttpFallbackCode(500), 'Http::500');
    });

    it('maps 502 to Http::502', () => {
        assert.strictEqual(getHttpFallbackCode(502), 'Http::502');
    });

    it('maps 503 to Http::503', () => {
        assert.strictEqual(getHttpFallbackCode(503), 'Http::503');
    });

    it('maps 504 to Http::504', () => {
        assert.strictEqual(getHttpFallbackCode(504), 'Http::504');
    });

    it('returns Internal::Server::Error for unknown status', () => {
        assert.strictEqual(getHttpFallbackCode(418), 'Internal::Server::Error');
    });

    it('extracts code directly from server response', () => {
        assert.strictEqual(extractServerCode({ code: 'Team::NotFound' }), 'Team::NotFound');
    });

    it('extracts code from nested error field', () => {
        assert.strictEqual(
            extractServerCode({ error: { code: 'Auth::Unauthorized' } }),
            'Auth::Unauthorized'
        );
    });

    it('extracts code from nested data field', () => {
        assert.strictEqual(
            extractServerCode({ data: { code: 'Container::NotFound' } }),
            'Container::NotFound'
        );
    });

    it('falls back to message when code is absent', () => {
        assert.strictEqual(extractServerCode({ message: 'Something went wrong' }), 'Something went wrong');
    });

    it('returns undefined for non-object responses', () => {
        assert.strictEqual(extractServerCode(null), undefined);
        assert.strictEqual(extractServerCode(42), undefined);
    });

    describe('ApiError', () => {
        it('stores code, status and originalError', () => {
            const cause = new Error('original');
            const err = new ApiError('Http::404', 404, cause);

            assert.strictEqual(err.code, 'Http::404');
            assert.strictEqual(err.status, 404);
            assert.strictEqual(err.originalError, cause);
            assert.ok(err instanceof Error);
            assert.strictEqual(err.name, 'ApiError');
        });

        it('isPermissionDenied returns true for RBAC error codes', () => {
            const err = new ApiError('Http::403');
            assert.ok(err.isPermissionDenied());
        });

        it('isPermissionDenied returns false for non-permission codes', () => {
            const err = new ApiError('Http::404');
            assert.ok(!err.isPermissionDenied());
        });

        it('ApiError.isRBACError identifies permission-denied errors', () => {
            const rbac = new ApiError('Team::AccessDenied', 403);
            const other = new ApiError('Http::404', 404);

            assert.ok(ApiError.isRBACError(rbac));
            assert.ok(!ApiError.isRBACError(other));
            assert.ok(!ApiError.isRBACError(new Error('plain error')));
        });
    });
});
