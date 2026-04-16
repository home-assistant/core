"""Tests for coordinator.py — BlancoDataUpdateCoordinator and helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from blanco_smart_home_api_client import BlancoApiClient
from blanco_smart_home_api_client.mask import mask_dev_id, mask_headers
import pytest

from homeassistant.components.blanco.definitions import BlancoDeviceType
from homeassistant.config_entries import ConfigEntryAuthFailed

from .conftest import make_coordinator, make_get_response

# ── Sample API response payloads ───────────────────────────────────────────────

SYSTEM_RESPONSE = {
    "results": [{"dev_name": "My BLANCO", "sw_ver_comm_con": "1.0"}],
    "info": {"connected": True, "online": 1700000000000, "dev_type": 2},
}
STATUS_RESPONSE = {
    "results": [{"co2_rest": 75, "filter_rest": 50}],
    "info": {},
}
SETTINGS_RESPONSE = {
    "results": [{"set_point_cooling": 8, "set_point_heating": 85}],
    "info": {},
}
ERRORS_RESPONSE = {"results": [], "info": {}}


# ── mask_headers ──────────────────────────────────────────────────────────────


class TestMaskHeaders:
    """Tests for the mask_headers helper."""

    def test_authorization_longer_than_20_chars_is_truncated(self) -> None:
        """Values longer than 20 chars for Authorization are truncated to 20 + '...'."""
        headers = {"Authorization": "Bearer averylongtokenthatexceedslimit"}
        result = mask_headers(headers)
        assert result["Authorization"] == "Bearer averylongtoke..."
        assert len(result["Authorization"]) == 23  # 20 + len("...")

    def test_x_api_key_longer_than_20_chars_is_truncated(self) -> None:
        """Values longer than 20 chars for X-Api-Key are truncated."""
        headers = {"X-Api-Key": "averylongapikeyvalue12345"}
        result = mask_headers(headers)
        assert result["X-Api-Key"] == "averylongapikeyvalue..."

    def test_x_app_id_longer_than_20_chars_is_truncated(self) -> None:
        """Values longer than 20 chars for X-App-Id are truncated."""
        headers = {"X-App-Id": "app-id-that-is-way-too-long-for-display"}
        result = mask_headers(headers)
        assert result["X-App-Id"] == "app-id-that-is-way-t..."

    def test_sensitive_value_exactly_20_chars_is_unchanged(self) -> None:
        """Sensitive values of exactly 20 chars are returned unchanged."""
        headers = {"Authorization": "exactly20charsvalue!"}
        assert len(headers["Authorization"]) == 20
        result = mask_headers(headers)
        assert result["Authorization"] == "exactly20charsvalue!"

    def test_sensitive_value_shorter_than_20_chars_is_unchanged(self) -> None:
        """Sensitive values shorter than 20 chars are returned unchanged."""
        headers = {"X-Api-Key": "shortkey"}
        result = mask_headers(headers)
        assert result["X-Api-Key"] == "shortkey"

    def test_non_sensitive_key_is_unchanged(self) -> None:
        """Non-sensitive header values are never modified."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        result = mask_headers(headers)
        assert result == headers

    def test_mixed_headers(self) -> None:
        """Only sensitive keys are truncated when headers contain a mix."""
        headers = {
            "Authorization": "Bearer averylongtokenthatexceedslimit",
            "Content-Type": "application/json",
        }
        result = mask_headers(headers)
        assert result["Authorization"].endswith("...")
        assert result["Content-Type"] == "application/json"


# ── _static_headers ───────────────────────────────────────────────────────────


class TestStaticHeaders:
    """Tests for the _static_headers instance variable of BlancoApiClient.

    _STATIC_HEADERS is no longer a module-level constant — it is built per
    BlancoApiClient instance from the constructor parameters app_version,
    app_build, and os_version.  Tests verify both the fixed values (User-Agent,
    X-OS-Type) and that constructor arguments flow through correctly.
    """

    def test_static_headers_keys_present(self, mock_hass: MagicMock) -> None:
        """_static_headers must define all required standard keys."""
        coord = make_coordinator(mock_hass)
        headers = coord._api._static_headers
        assert "User-Agent" in headers
        assert "X-App-Version" in headers
        assert "X-App-Build" in headers
        assert "X-OS-Type" in headers
        assert "X-OS-Version" in headers

    def test_user_agent_value(self, mock_hass: MagicMock) -> None:
        """User-Agent must be the fixed identifier string 'ha-blanco'."""
        coord = make_coordinator(mock_hass)
        assert coord._api._static_headers["User-Agent"] == "ha-blanco"

    def test_os_type_value(self, mock_hass: MagicMock) -> None:
        """X-OS-Type must always be 'HomeAssistant'."""
        coord = make_coordinator(mock_hass)
        assert coord._api._static_headers["X-OS-Type"] == "HomeAssistant"

    def test_app_version_passed_to_static_headers(self) -> None:
        """app_version passed to BlancoApiClient must appear in X-App-Version."""
        client = BlancoApiClient(MagicMock(), app_version="9.9.9", app_build="42")
        assert client._static_headers["X-App-Version"] == "9.9.9"

    def test_app_build_passed_to_static_headers(self) -> None:
        """app_build passed to BlancoApiClient must appear in X-App-Build."""
        client = BlancoApiClient(MagicMock(), app_version="9.9.9", app_build="42")
        assert client._static_headers["X-App-Build"] == "42"

    def test_os_version_passed_to_static_headers(self) -> None:
        """os_version passed to BlancoApiClient must appear in X-OS-Version."""
        client = BlancoApiClient(MagicMock(), os_version="2026.1.0")
        assert client._static_headers["X-OS-Version"] == "2026.1.0"

    def test_api_client_auth_headers_include_static_headers(
        self, mock_hass: MagicMock
    ) -> None:
        """API client auth headers must contain all _static_headers keys and values."""
        coord = make_coordinator(mock_hass)
        auth_headers = coord._api._auth_headers()
        for key, value in coord._api._static_headers.items():
            assert auth_headers.get(key) == value, (
                f"Expected _auth_headers()[{key!r}] == {value!r}, "
                f"got {auth_headers.get(key)!r}"
            )

    @pytest.mark.asyncio
    async def test_renewal_request_includes_static_headers(
        self, mock_hass: MagicMock
    ) -> None:
        """The token-renewal POST must include all _static_headers."""
        renewal_body = {
            "results": [{"token": "new-token", "token_type": "Bearer"}],
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=renewal_body)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post.return_value = cm

        coord = make_coordinator(mock_hass, session=mock_session)
        await coord._async_renew_token()

        _, call_kwargs = mock_session.post.call_args
        sent_headers: dict[str, str] = call_kwargs.get("headers", {})
        for key, value in coord._api._static_headers.items():
            assert sent_headers.get(key) == value, (
                f"Renewal POST missing header {key!r}={value!r}"
            )


# ── mask_dev_id ───────────────────────────────────────────────────────────────


class TestMaskDevId:
    """Tests for the mask_dev_id helper."""

    def test_longer_than_8_chars_shows_first_8_plus_ellipsis(self) -> None:
        """Values longer than 8 chars expose only the first 8 chars."""
        result = mask_dev_id("abc123devid")
        assert result == "abc123de..."

    def test_exactly_8_chars_unchanged(self) -> None:
        """A value of exactly 8 chars is returned unchanged."""
        result = mask_dev_id("12345678")
        assert result == "12345678"

    def test_shorter_than_8_chars_unchanged(self) -> None:
        """A value shorter than 8 chars is returned unchanged."""
        result = mask_dev_id("abc")
        assert result == "abc"

    def test_none_returns_empty_string(self) -> None:
        """None input returns an empty string."""
        assert mask_dev_id(None) == ""

    def test_empty_string_returns_empty_string(self) -> None:
        """An empty string input returns an empty string."""
        assert mask_dev_id("") == ""


# ── _async_update_data ─────────────────────────────────────────────────────────


class TestAsyncUpdateData:
    """Async integration tests for BlancoDataUpdateCoordinator._async_update_data."""

    def _make_session(self, *responses: MagicMock) -> MagicMock:
        """Return a mock aiohttp session whose .get() yields *responses* in order."""
        session = MagicMock()
        session.get.side_effect = list(responses)
        return session

    @pytest.mark.asyncio
    async def test_all_endpoints_200_returns_structured_data(
        self, mock_hass: MagicMock
    ) -> None:
        """All four endpoints returning 200 produces a correctly structured data dict."""
        session = self._make_session(
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(200, STATUS_RESPONSE),
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
        )
        coord = make_coordinator(mock_hass, session=session)
        data = await coord._async_update_data()

        assert "system" in data
        assert "status" in data
        assert "settings" in data
        assert "errors" in data
        assert "actions" not in data
        assert "stats" not in data
        assert data["system"]["params"]["dev_name"] == "My BLANCO"
        assert data["status"]["params"]["co2_rest"] == 75
        assert data["settings"]["params"]["set_point_cooling"] == 8
        assert data["errors"]["errors"] == []

    @pytest.mark.asyncio
    async def test_one_endpoint_500_uses_previous_data_for_that_key(
        self, mock_hass: MagicMock
    ) -> None:
        """A 500 on /status falls back to previous coordinator data for that key."""
        session = self._make_session(
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(500, {}),  # /status fails
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
        )
        coord = make_coordinator(mock_hass, session=session)
        # Seed previous data so the fallback has something to return.
        coord.data = {
            "system": {"params": {}, "info": {}},
            "status": {"params": {"co2_rest": 99}, "info": {}},
            "settings": {"params": {}, "info": {}},
            "errors": {"errors": [], "info": {}},
        }
        data = await coord._async_update_data()

        # The previous status data is used as fallback.
        assert data["status"]["params"]["co2_rest"] == 99
        # Other endpoints still return fresh data.
        assert data["system"]["params"]["dev_name"] == "My BLANCO"

    @pytest.mark.asyncio
    async def test_401_with_successful_renewal_retries_and_succeeds(
        self, mock_hass: MagicMock
    ) -> None:
        """A 401 on /system triggers renewal; success causes the request to be retried."""
        session = self._make_session(
            make_get_response(401, {}),  # /system — expired token
            make_get_response(200, SYSTEM_RESPONSE),  # /system — retry after renewal
            make_get_response(200, STATUS_RESPONSE),
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
        )
        coord = make_coordinator(mock_hass, session=session)
        with patch.object(coord, "_async_renew_token", AsyncMock(return_value=True)):
            data = await coord._async_update_data()

        assert data["system"]["params"]["dev_name"] == "My BLANCO"

    @pytest.mark.asyncio
    async def test_401_with_failed_renewal_raises_config_entry_auth_failed(
        self, mock_hass: MagicMock
    ) -> None:
        """A 401 on /system where renewal also fails raises ConfigEntryAuthFailed."""
        session = self._make_session(
            make_get_response(401, {}),  # /system — expired token, no retry
        )
        coord = make_coordinator(mock_hass, session=session)
        with (
            patch.object(coord, "_async_renew_token", AsyncMock(return_value=False)),
            pytest.raises(ConfigEntryAuthFailed),
        ):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_dev_type_discovered_from_system_info(
        self, mock_hass: MagicMock
    ) -> None:
        """dev_type is discovered from the system info block when not yet known."""
        session = self._make_session(
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(200, STATUS_RESPONSE),
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
        )
        # Create a coordinator with dev_type=None to trigger discovery.
        coord = make_coordinator(
            mock_hass, session=session, dev_type=BlancoDeviceType.SODA2
        )
        coord.dev_type = None
        await coord._async_update_data()

        # SYSTEM_RESPONSE has dev_type=2 (AIO).
        assert coord.dev_type == BlancoDeviceType.AIO


# ── _async_renew_token ─────────────────────────────────────────────────────────


class TestAsyncRenewToken:
    """Async tests for BlancoDataUpdateCoordinator._async_renew_token."""

    @pytest.mark.asyncio
    async def test_successful_post_returns_true_and_updates_auth_header(
        self, mock_hass: MagicMock
    ) -> None:
        """A 200 renewal response returns True and updates the Authorization header."""
        renewal_body = {
            "results": [{"token": "new-token-value", "token_type": "Bearer"}],
            "errors": None,
            "info": None,
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=renewal_body)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post.return_value = cm

        coord = make_coordinator(mock_hass, session=mock_session)
        result = await coord._async_renew_token()

        assert result is True
        assert coord._api._auth_headers()["Authorization"] == "Bearer new-token-value"

    @pytest.mark.asyncio
    async def test_non_200_post_returns_false(self, mock_hass: MagicMock) -> None:
        """A non-200 renewal response returns False."""
        mock_resp = AsyncMock()
        mock_resp.status = 401
        mock_resp.json = AsyncMock(return_value={"results": []})
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post.return_value = cm

        coord = make_coordinator(mock_hass, session=mock_session)
        result = await coord._async_renew_token()

        assert result is False
