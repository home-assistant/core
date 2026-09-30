"""Tests for coordinator.py — BlancoDataUpdateCoordinator and helpers."""

from unittest.mock import MagicMock

from blanco_smart_home_api_client import (
    BlancoApiClient,
    BlancoConnectionError,
    HttpStatus,
)
from blanco_smart_home_api_client.mask import mask_dev_id, mask_headers
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.blanco.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import make_coordinator, make_get_response

from tests.common import MockConfigEntry, async_fire_time_changed


def _entry_states(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entry_id: str
) -> dict[str, str]:
    """Return the current state of every entity belonging to the config entry."""
    return {
        entity.entity_id: hass.states.get(entity.entity_id).state
        for entity in er.async_entries_for_config_entry(entity_registry, entry_id)
    }


@pytest.mark.parametrize(
    ("failing_endpoint", "failure"),
    [
        pytest.param(
            "get_device_system",
            (HttpStatus.INTERNAL_SERVER_ERROR, {}),
            id="system_http_error",
        ),
        pytest.param(
            "get_device_system",
            BlancoConnectionError("timeout"),
            id="system_connection_error",
        ),
        pytest.param(
            "get_device_errors",
            (HttpStatus.INTERNAL_SERVER_ERROR, {}),
            id="errors_http_error",
        ),
        pytest.param(
            "get_device_errors",
            BlancoConnectionError("timeout"),
            id="errors_connection_error",
        ),
    ],
)
async def test_failing_endpoint_keeps_previous_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_blanco_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    failing_endpoint: str,
    failure: tuple[int, dict] | Exception,
) -> None:
    """Test one failing endpoint keeps its previous data while the other refreshes."""
    await setup_integration(hass, mock_config_entry)
    states_before = _entry_states(hass, entity_registry, mock_config_entry.entry_id)

    getattr(mock_blanco_client, failing_endpoint).side_effect = [failure]
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    getattr(mock_blanco_client, failing_endpoint).assert_awaited()
    assert STATE_UNAVAILABLE not in states_before.values()
    assert (
        _entry_states(hass, entity_registry, mock_config_entry.entry_id)
        == states_before
    )


async def test_all_endpoints_failing_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_blanco_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable when neither endpoint returns fresh data."""
    await setup_integration(hass, mock_config_entry)

    mock_blanco_client.get_device_system.side_effect = BlancoConnectionError("timeout")
    mock_blanco_client.get_device_errors.side_effect = BlancoConnectionError("timeout")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    states = _entry_states(hass, entity_registry, mock_config_entry.entry_id)
    assert states
    assert set(states.values()) == {STATE_UNAVAILABLE}


SYSTEM_RESPONSE = {
    "results": [{"dev_name": "My BLANCO", "sw_ver_comm_con": "1.0"}],
    "info": {"connected": True, "online": 1700000000000, "dev_type": 2},
}
ERRORS_RESPONSE = {"results": [], "info": {}}
AUTH_RESPONSE = {
    "results": [{"token": "renewed-token", "token_type": "Bearer"}],
    "info": {},
}


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
