"""Tests for the mijn-ista API client library."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from mijn_ista_api import MijnIstaAPI, MijnIstaAuthError, MijnIstaConnectionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status: int = 200, json_data: dict | None = None):
    """Build a mock aiohttp response usable as an async context manager."""
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    if status >= 400:
        resp.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                MagicMock(), (), status=status
            )
        )
    else:
        resp.raise_for_status = MagicMock()
    return resp


def _mock_session(response):
    """Wrap a response mock so session.post() works as an async context manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post = MagicMock(return_value=cm)
    return session


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestAuthenticate:
    async def test_success_stores_jwt(self):
        resp = _mock_response(200, {"JWT": "my-jwt-token"})
        session = _mock_session(resp)
        api = MijnIstaAPI(session, "user@example.com", "secret")
        await api.authenticate()
        assert api._jwt == "my-jwt-token"

    async def test_http_400_raises_auth_error(self):
        resp = _mock_response(400, {})
        session = _mock_session(resp)
        api = MijnIstaAPI(session, "user@example.com", "wrong")
        with pytest.raises(MijnIstaAuthError):
            await api.authenticate()

    async def test_network_error_raises_connection_error(self):
        session = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("network down"))
        cm.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=cm)
        api = MijnIstaAPI(session, "user@example.com", "secret")
        with pytest.raises(MijnIstaConnectionError):
            await api.authenticate()

    async def test_timeout_raises_connection_error(self):
        session = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError)
        cm.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=cm)
        api = MijnIstaAPI(session, "user@example.com", "secret")
        with pytest.raises(MijnIstaConnectionError):
            await api.authenticate()

    async def test_missing_jwt_in_response_raises_auth_error(self):
        resp = _mock_response(200, {"SomethingElse": "value"})
        session = _mock_session(resp)
        api = MijnIstaAPI(session, "user@example.com", "secret")
        with pytest.raises(MijnIstaAuthError):
            await api.authenticate()


# ---------------------------------------------------------------------------
# JWT refresh / absorption
# ---------------------------------------------------------------------------


class TestJWTRefresh:
    async def test_response_jwt_is_absorbed(self):
        """Every successful response should update the stored JWT."""
        auth_resp = _mock_response(200, {"JWT": "initial-jwt"})
        auth_session = _mock_session(auth_resp)
        api = MijnIstaAPI(auth_session, "u", "p")
        await api.authenticate()
        assert api._jwt == "initial-jwt"

        # Now simulate a data endpoint returning a refreshed JWT
        data_resp = _mock_response(200, {"JWT": "refreshed-jwt", "Cus": []})
        api._session = _mock_session(data_resp)
        result = await api.get_user_values()
        assert api._jwt == "refreshed-jwt"
        assert result["Cus"] == []

    async def test_no_jwt_in_response_keeps_existing(self):
        """If a response has no JWT field, the stored JWT must not change."""
        auth_resp = _mock_response(200, {"JWT": "original-jwt"})
        api = MijnIstaAPI(_mock_session(auth_resp), "u", "p")
        await api.authenticate()

        data_resp = _mock_response(200, {"data": "value"})  # no JWT key
        api._session = _mock_session(data_resp)
        await api.get_user_values()
        assert api._jwt == "original-jwt"


# ---------------------------------------------------------------------------
# 401 retry mechanism
# ---------------------------------------------------------------------------


class TestRetryOn401:
    async def test_401_triggers_reauth_and_retries(self):
        """A 401 response should trigger re-authentication and one retry."""
        call_count = 0

        async def _fake_post_enter(self_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: 401
                resp = _mock_response(401, {})
                return resp
            elif call_count == 2:
                # Re-auth call: 200 with new JWT
                return _mock_response(200, {"JWT": "new-jwt"})
            else:
                # Retry call: 200 with data
                return _mock_response(200, {"JWT": "new-jwt", "Cus": []})

        session = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = _fake_post_enter
        cm.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=cm)

        api = MijnIstaAPI(session, "u", "p", lang="en-GB")
        api._jwt = "old-jwt"
        result = await api.get_user_values()
        assert result.get("Cus") == []


# ---------------------------------------------------------------------------
# Request body construction
# ---------------------------------------------------------------------------


class TestRequestBody:
    def test_body_merges_jwt_and_lang(self):
        api = MijnIstaAPI(MagicMock(), "u", "p", lang="nl-NL")
        api._jwt = "tok"
        body = api._body({"extra": "val"})
        assert body == {"JWT": "tok", "LANG": "nl-NL", "extra": "val"}

    def test_body_extra_overrides_nothing_unexpectedly(self):
        api = MijnIstaAPI(MagicMock(), "u", "p", lang="en-GB")
        api._jwt = "tok"
        body = api._body({"Cuid": "abc"})
        assert body["Cuid"] == "abc"
        assert body["JWT"] == "tok"


# ---------------------------------------------------------------------------
# Endpoint convenience methods
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 425 / 503 retry mechanism
# ---------------------------------------------------------------------------


class TestRetryOn425And503:
    async def test_425_retries_and_succeeds(self):
        """A 425 response should trigger a retry; success on second attempt."""
        responses = [
            _mock_response(425, {}),
            _mock_response(200, {"Cus": []}),
        ]
        call_idx = 0

        async def _enter(_):
            nonlocal call_idx
            r = responses[call_idx]
            call_idx += 1
            return r

        session = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = _enter
        cm.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=cm)

        api = MijnIstaAPI(session, "u", "p")
        api._jwt = "tok"
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await api.get_user_values()
        assert result.get("Cus") == []

    async def test_503_retries_and_succeeds(self):
        responses = [
            _mock_response(503, {}),
            _mock_response(200, {"Cus": []}),
        ]
        call_idx = 0

        async def _enter(_):
            nonlocal call_idx
            r = responses[call_idx]
            call_idx += 1
            return r

        session = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = _enter
        cm.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=cm)

        api = MijnIstaAPI(session, "u", "p")
        api._jwt = "tok"
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await api.get_user_values()
        assert result.get("Cus") == []

    async def test_persistent_425_raises_connection_error(self):
        """Four consecutive 425 responses should raise MijnIstaConnectionError."""
        async def _enter(_):
            return _mock_response(425, {})

        session = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = _enter
        cm.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=cm)

        api = MijnIstaAPI(session, "u", "p")
        api._jwt = "tok"
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(MijnIstaConnectionError):
                await api.get_user_values()


# ---------------------------------------------------------------------------
# JWT refresh endpoint
# ---------------------------------------------------------------------------


class TestJWTRefresh:
    async def test_refresh_jwt_updates_stored_jwt(self):
        resp = _mock_response(200, {"JWT": "refreshed-tok"})
        api = MijnIstaAPI(_mock_session(resp), "u", "p")
        api._jwt = "old-tok"
        await api._refresh_jwt()
        assert api._jwt == "refreshed-tok"

    async def test_refresh_jwt_falls_back_to_full_auth_when_endpoint_fails(self):
        """If JWTRefresh returns no JWT, fall back to full authenticate()."""
        resp = _mock_response(200, {})  # no JWT field
        api = MijnIstaAPI(_mock_session(resp), "u", "p")
        api._jwt = "old-tok"
        api.authenticate = AsyncMock()
        await api._refresh_jwt()
        api.authenticate.assert_called_once()

    async def test_refresh_jwt_falls_back_on_network_error(self):
        session = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("err"))
        cm.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=cm)
        api = MijnIstaAPI(session, "u", "p")
        api._jwt = "old-tok"
        api.authenticate = AsyncMock()
        await api._refresh_jwt()
        api.authenticate.assert_called_once()

    async def test_401_uses_refresh_not_full_auth(self):
        """On 401, _refresh_jwt should be called, not authenticate directly."""
        responses = [
            _mock_response(401, {}),
            _mock_response(200, {"JWT": "new-tok", "Cus": []}),
        ]
        call_idx = 0

        async def _enter(_):
            nonlocal call_idx
            r = responses[call_idx]
            call_idx += 1
            return r

        session = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = _enter
        cm.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=cm)

        api = MijnIstaAPI(session, "u", "p")
        api._jwt = "old-tok"
        api._refresh_jwt = AsyncMock(side_effect=lambda: setattr(api, "_jwt", "new-tok") or None)
        result = await api.get_user_values()
        api._refresh_jwt.assert_called_once()
        assert result.get("Cus") == []


# ---------------------------------------------------------------------------
# MonthValues shard polling
# ---------------------------------------------------------------------------


class TestMonthValuesShardsPolling:
    async def test_polls_until_shards_loaded(self):
        """Should re-poll when hs < sh, stop when hs >= sh."""
        responses = [
            _mock_response(200, {"hs": 1, "sh": 3, "mc": []}),  # not done
            _mock_response(200, {"hs": 2, "sh": 3, "mc": []}),  # not done
            _mock_response(200, {"hs": 3, "sh": 3, "mc": [{"y": 2024, "m": 11}]}),  # done
        ]
        call_idx = 0

        async def _enter(_):
            nonlocal call_idx
            r = responses[call_idx]
            call_idx += 1
            return r

        session = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = _enter
        cm.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=cm)

        api = MijnIstaAPI(session, "u", "p")
        api._jwt = "tok"
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await api.get_month_values("cuid-1")

        assert result["hs"] == 3
        assert len(result["mc"]) == 1
        assert mock_sleep.call_count == 2  # slept twice between 3 polls

    async def test_returns_immediately_when_no_shards(self):
        """sh == 0 means no shard info; return immediately."""
        resp = _mock_response(200, {"sh": 0, "hs": 0, "mc": []})
        api = MijnIstaAPI(_mock_session(resp), "u", "p")
        api._jwt = "tok"
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await api.get_month_values("cuid-1")
        assert mock_sleep.call_count == 0
        assert result["mc"] == []

    async def test_returns_after_max_polls(self):
        """After 15 re-polls, return whatever we have."""
        async def _enter(_):
            return _mock_response(200, {"hs": 1, "sh": 99, "mc": []})

        session = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = _enter
        cm.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=cm)

        api = MijnIstaAPI(session, "u", "p")
        api._jwt = "tok"
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await api.get_month_values("cuid-1")
        # 1 initial + 15 re-polls = 16 total; 15 sleeps
        assert mock_sleep.call_count == 15
        assert result["mc"] == []


class TestEndpoints:
    @pytest.fixture
    def api_with_jwt(self):
        api = MijnIstaAPI(MagicMock(), "u", "p")
        api._jwt = "tok"
        return api

    async def test_get_user_values_posts_to_correct_path(self, api_with_jwt):
        resp = _mock_response(200, {"DisplayName": "Test"})
        api_with_jwt._session = _mock_session(resp)
        result = await api_with_jwt.get_user_values()
        assert result["DisplayName"] == "Test"
        url = api_with_jwt._session.post.call_args[0][0]
        assert "/api/Values/UserValues" in url

    async def test_get_month_values_sends_cuid(self, api_with_jwt):
        resp = _mock_response(200, {"mc": []})
        api_with_jwt._session = _mock_session(resp)
        await api_with_jwt.get_month_values("my-cuid")
        body = api_with_jwt._session.post.call_args[1]["json"]
        assert body["Cuid"] == "my-cuid"

    async def test_get_consumption_averages_sends_par(self, api_with_jwt):
        resp = _mock_response(200, {"Averages": []})
        api_with_jwt._session = _mock_session(resp)
        await api_with_jwt.get_consumption_averages("cuid-1", "2024-01-01", "2024-12-31")
        body = api_with_jwt._session.post.call_args[1]["json"]
        assert body["PAR"]["start"] == "2024-01-01"
        assert body["PAR"]["end"] == "2024-12-31"
        assert body["PAR"]["cuid"] == "cuid-1"
