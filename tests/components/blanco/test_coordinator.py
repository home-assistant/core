"""Tests for coordinator.py — BlancoDataUpdateCoordinator and helpers."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

from blanco_smart_home_api_client import BlancoApiClient, BlancoConnectionError
from blanco_smart_home_api_client.mask import mask_dev_id, mask_headers
import pytest

from homeassistant.components.blanco.const import CONF_APP_LOCALE
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import Event

from .conftest import make_coordinator, make_get_response, make_mock_entry

# ── Sample API response payloads ───────────────────────────────────────────────

SYSTEM_RESPONSE = {
    "results": [{"dev_name": "My BLANCO", "sw_ver_comm_con": "1.0"}],
    "info": {"connected": True, "online": 1700000000000, "dev_type": 2},
}
ERRORS_RESPONSE = {"results": [], "info": {}}
AUTH_RESPONSE = {
    "results": [{"token": "renewed-token", "token_type": "Bearer"}],
    "info": {},
}


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

    async def test_all_endpoints_200_returns_structured_data(
        self, mock_hass: MagicMock
    ) -> None:
        """Both endpoints returning 200 produces a correctly structured data dict."""
        session = self._make_session(
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
        )
        coord = make_coordinator(mock_hass, session=session)
        data = await coord._async_update_data()

        assert "system" in data
        assert "errors" in data
        assert "status" not in data
        assert "settings" not in data
        assert "actions" not in data
        assert "stats" not in data
        assert data["system"]["params"]["dev_name"] == "My BLANCO"
        assert data["errors"]["errors"] == []

    async def test_one_endpoint_500_uses_previous_data_for_that_key(
        self, mock_hass: MagicMock
    ) -> None:
        """A 500 on /errors falls back to previous coordinator data for that key."""
        session = self._make_session(
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(500, {}),  # /errors fails
        )
        coord = make_coordinator(mock_hass, session=session)
        # Seed previous data so the fallback has something to return.
        coord.data = {
            "system": {"params": {}, "info": {}},
            "errors": {"errors": [{"err_code": 1}], "info": {}},
        }
        data = await coord._async_update_data()

        # The previous errors data is used as fallback.
        assert data["errors"]["errors"] == [{"err_code": 1}]
        # The other endpoint still returns fresh data.
        assert data["system"]["params"]["dev_name"] == "My BLANCO"

    async def test_401_with_successful_renewal_retries_and_succeeds(
        self, mock_hass: MagicMock
    ) -> None:
        """A 401 on /system triggers renewal; success causes the request to be retried."""
        session = self._make_session(
            make_get_response(401, {}),  # /system — expired token
            make_get_response(200, SYSTEM_RESPONSE),  # /system — retry after renewal
            make_get_response(200, ERRORS_RESPONSE),
        )
        session.post.side_effect = [make_get_response(200, AUTH_RESPONSE)]
        coord = make_coordinator(mock_hass, session=session)
        data = await coord._async_update_data()

        assert data["system"]["params"]["dev_name"] == "My BLANCO"

    async def test_401_with_failed_renewal_raises_config_entry_auth_failed(
        self, mock_hass: MagicMock
    ) -> None:
        """A 401 on /system where renewal also fails raises ConfigEntryAuthFailed."""
        session = self._make_session(
            make_get_response(401, {}),  # /system — expired token, no retry
        )
        session.post.side_effect = [make_get_response(401, {})]  # renewal also fails
        coord = make_coordinator(mock_hass, session=session)

        with pytest.raises(ConfigEntryAuthFailed):
            await coord._async_update_data()


# ── language listener ───────────────────────────────────────────────────────────


class TestLanguageListener:
    """Tests for the HA-language → BLANCO API locale sync listener."""

    def _get_registered_callback(
        self, mock_hass: MagicMock
    ) -> Callable[[Event], Awaitable[None]]:
        """Return the callback the coordinator registered for EVENT_CORE_CONFIG_UPDATE."""
        assert mock_hass.bus.async_listen.call_count == 1
        event_type, callback = mock_hass.bus.async_listen.call_args[0]
        assert event_type == EVENT_CORE_CONFIG_UPDATE
        return callback

    async def test_registers_listener_on_init(self, mock_hass: MagicMock) -> None:
        """The coordinator registers exactly one EVENT_CORE_CONFIG_UPDATE listener."""
        make_coordinator(mock_hass)
        self._get_registered_callback(mock_hass)

    async def test_ignores_event_without_language_key(
        self, mock_hass: MagicMock
    ) -> None:
        """An event whose data has no 'language' key is ignored."""
        coord = make_coordinator(mock_hass)
        callback = self._get_registered_callback(mock_hass)
        coord._api.update_app_locale = AsyncMock()

        await callback(MagicMock(data={}))

        coord._api.update_app_locale.assert_not_called()

    async def test_ignores_unchanged_locale(self, mock_hass: MagicMock) -> None:
        """No API call is made when the new locale matches the stored one."""
        entry = make_mock_entry(data={CONF_APP_LOCALE: "de"})
        mock_hass.config.language = "de-DE"
        coord = make_coordinator(mock_hass, entry=entry)
        callback = self._get_registered_callback(mock_hass)
        coord._api.update_app_locale = AsyncMock()

        await callback(MagicMock(data={"language": "de"}))

        coord._api.update_app_locale.assert_not_called()

    async def test_updates_locale_on_change(self, mock_hass: MagicMock) -> None:
        """A changed locale is PUT to the API and persisted into entry.data."""
        entry = make_mock_entry(data={CONF_APP_LOCALE: "en"})
        mock_hass.config.language = "de-DE"
        coord = make_coordinator(mock_hass, entry=entry)
        callback = self._get_registered_callback(mock_hass)
        coord._api.update_app_locale = AsyncMock(return_value=True)

        await callback(MagicMock(data={"language": "de"}))

        coord._api.update_app_locale.assert_awaited_once_with("de")
        mock_hass.config_entries.async_update_entry.assert_called_once()
        _, kwargs = mock_hass.config_entries.async_update_entry.call_args
        assert kwargs["data"][CONF_APP_LOCALE] == "de"

    async def test_does_not_persist_when_api_reports_failure(
        self, mock_hass: MagicMock
    ) -> None:
        """entry.data is left untouched when the API reports a non-2xx status."""
        entry = make_mock_entry(data={CONF_APP_LOCALE: "en"})
        mock_hass.config.language = "de-DE"
        coord = make_coordinator(mock_hass, entry=entry)
        callback = self._get_registered_callback(mock_hass)
        coord._api.update_app_locale = AsyncMock(return_value=False)

        await callback(MagicMock(data={"language": "de"}))

        mock_hass.config_entries.async_update_entry.assert_not_called()

    async def test_swallows_connection_error(self, mock_hass: MagicMock) -> None:
        """A BlancoConnectionError from the API call is swallowed, not raised."""
        entry = make_mock_entry(data={CONF_APP_LOCALE: "en"})
        mock_hass.config.language = "de-DE"
        coord = make_coordinator(mock_hass, entry=entry)
        callback = self._get_registered_callback(mock_hass)
        coord._api.update_app_locale = AsyncMock(
            side_effect=BlancoConnectionError("boom")
        )

        await callback(MagicMock(data={"language": "de"}))  # must not raise

        mock_hass.config_entries.async_update_entry.assert_not_called()
