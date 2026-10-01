"""Test the GKP integration initialization."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from gkphomepython import (
    USER_CONNECTED_INTERVAL,
    USER_CONNECTED_REPORT_DELAY,
    GkpAuthError,
    GkpConnectionError,
    GkpDeviceError,
    GkpError,
    GkpMode,
    GkpRateLimitError,
)
from gkphomepython.const import FIRST_REPORT_TIMEOUT, OFFLINE_AFTER
import pytest

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.gkp.const import (
    DISCOVERY_INTERVAL,
    DOMAIN,
    FAST_POLLING_INTERVAL,
    OAUTH2_TOKEN,
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import setup_integration
from .conftest import BEDROOM_ID, LIVING_ROOM_ID

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

LIVING_ROOM_ENTITY_ID = "climate.living_room"
BEDROOM_ENTITY_ID = "climate.bedroom"


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    """Move time forward and run the scheduled updates."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _expired_token_entry() -> MockConfigEntry:
    """Return a config entry whose token must be refreshed."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-user-id",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 0,
            },
        },
    )


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload of entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_gkp_client.get_installations.assert_called_once()
    mock_gkp_client.notify_user_connected.assert_called_once_with("installation-1")
    assert mock_gkp_client.get_thermostat.call_count == 2

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("token_response", "expected_state"),
    [
        pytest.param({"status": 401}, ConfigEntryState.SETUP_ERROR, id="auth_failed"),
        pytest.param({"status": 500}, ConfigEntryState.SETUP_RETRY, id="server_error"),
        pytest.param(
            {"exc": ClientError("Connection timeout")},
            ConfigEntryState.SETUP_RETRY,
            id="network_error",
        ),
    ],
)
async def test_setup_entry_token_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    token_response: dict[str, Any],
    expected_state: ConfigEntryState,
) -> None:
    """Test setup when the token cannot be refreshed."""
    config_entry = _expired_token_entry()
    config_entry.add_to_hass(hass)
    aioclient_mock.post(OAUTH2_TOKEN, **token_response)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is expected_state


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (GkpAuthError("Auth failed"), ConfigEntryState.SETUP_ERROR),
        (GkpConnectionError("Connection lost"), ConfigEntryState.SETUP_RETRY),
        (GkpError("API error"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_discovery_errors(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup errors during installation discovery."""
    mock_gkp_client.get_installations.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_setup_entry_all_devices_failing(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup is retried when no device can be read."""
    mock_gkp_client.get_thermostat.side_effect = GkpConnectionError("lost")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_without_devices(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    installations_data: list[dict[str, Any]],
) -> None:
    """Test setup succeeds for an account without installation."""
    installations_data.clear()

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_gkp_client.notify_user_connected.assert_not_called()
    mock_gkp_client.get_thermostat.assert_not_called()


async def test_user_connected_interval(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test devices are woken up every user connected interval only."""
    await setup_integration(hass, mock_config_entry)
    assert mock_gkp_client.notify_user_connected.call_count == 1

    await _tick(hass, freezer, USER_CONNECTED_INTERVAL - UPDATE_INTERVAL)
    assert mock_gkp_client.notify_user_connected.call_count == 1

    await _tick(hass, freezer, UPDATE_INTERVAL)
    assert mock_gkp_client.notify_user_connected.call_count == 2


async def test_refresh_after_user_connected(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the devices are read again shortly after being woken up."""
    await setup_integration(hass, mock_config_entry)
    assert mock_gkp_client.get_thermostat.call_count == 2

    await _tick(hass, freezer, USER_CONNECTED_REPORT_DELAY)
    assert mock_gkp_client.get_thermostat.call_count == 4

    # Back to the regular interval once the answer was read
    await _tick(hass, freezer, USER_CONNECTED_REPORT_DELAY)
    assert mock_gkp_client.get_thermostat.call_count == 4


async def test_available_until_first_report_timeout(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_contents: dict[str, dict[str, Any]],
) -> None:
    """Test devices with an old report are only judged once woken up."""
    device_contents[LIVING_ROOM_ID]["Dd"]["value"] = "30/9/2026 10:00:00"
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    await _tick(hass, freezer, FIRST_REPORT_TIMEOUT)
    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Later wake ups do not make a silent device available again
    await _tick(hass, freezer, USER_CONNECTED_INTERVAL)
    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    device_contents[LIVING_ROOM_ID]["Dd"]["value"] = "30/9/2026 14:18:00"
    await _tick(hass, freezer, USER_CONNECTED_REPORT_DELAY)
    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("exception", "has_reauth_flow"),
    [
        (GkpAuthError("expired"), True),
        (GkpConnectionError("lost"), False),
    ],
)
async def test_user_connected_errors(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
    has_reauth_flow: bool,
) -> None:
    """Test failures to wake up the devices."""
    await setup_integration(hass, mock_config_entry)
    mock_gkp_client.notify_user_connected.side_effect = exception
    mock_gkp_client.get_thermostat.reset_mock()

    await _tick(hass, freezer, USER_CONNECTED_INTERVAL)

    assert (
        any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        == has_reauth_flow
    )
    # A failed wake up does not prevent reading the devices
    assert mock_gkp_client.get_thermostat.called is not has_reauth_flow


async def test_dynamic_device_creation(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    installations_data: list[dict[str, Any]],
    device_contents: dict[str, dict[str, Any]],
) -> None:
    """Test new devices are created dynamically."""
    await setup_integration(hass, mock_config_entry)
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "AABBCCDDEE03"), mock_config_entry.entry_id
        )
        is None
    )

    installations_data[0]["rooms"].append(
        {"Rn": "Kitchen", "devices": [{"Id_deviceId": "AABBCCDDEE03"}]}
    )
    device_contents["AABBCCDDEE03"] = device_contents[LIVING_ROOM_ID]

    await _tick(hass, freezer, DISCOVERY_INTERVAL)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "AABBCCDDEE03"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Kitchen"
    assert hass.states.get("climate.kitchen") is not None


async def test_stale_device_removal(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    installations_data: list[dict[str, Any]],
) -> None:
    """Test devices removed from the installations are removed."""
    await setup_integration(hass, mock_config_entry)
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, BEDROOM_ID), mock_config_entry.entry_id
    )

    installations_data[0]["rooms"] = installations_data[0]["rooms"][:1]

    await _tick(hass, freezer, DISCOVERY_INTERVAL)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, BEDROOM_ID), mock_config_entry.entry_id
        )
        is None
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, LIVING_ROOM_ID), mock_config_entry.entry_id
    )


async def test_periodic_discovery_error(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed periodic discovery keeps the known devices."""
    await setup_integration(hass, mock_config_entry)
    mock_gkp_client.get_installations.side_effect = GkpConnectionError("lost")

    await _tick(hass, freezer, DISCOVERY_INTERVAL)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, BEDROOM_ID), mock_config_entry.entry_id
    )
    state = hass.states.get(BEDROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("exception", "has_reauth_flow"),
    [
        (GkpAuthError("expired"), True),
        (GkpConnectionError("lost"), False),
        (ValueError("unexpected"), False),
    ],
)
async def test_hub_coordinator_update_errors(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
    has_reauth_flow: bool,
) -> None:
    """Test hub coordinator handles errors during regular update."""
    await setup_integration(hass, mock_config_entry)
    mock_gkp_client.get_thermostat.side_effect = exception

    await _tick(hass, freezer, UPDATE_INTERVAL)

    # The entities keep their last known state when the hub update fails
    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes["current_temperature"] == 21.1
    assert (
        any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        == has_reauth_flow
    )


async def test_single_device_error_keeps_others(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_contents: dict[str, dict[str, Any]],
) -> None:
    """Test one failing device does not prevent updating the others."""
    await setup_integration(hass, mock_config_entry)
    get_thermostat = mock_gkp_client.get_thermostat.side_effect

    async def fail_for_bedroom(device_id: str, installation: Any) -> Any:
        if device_id == BEDROOM_ID:
            raise GkpDeviceError("not found")
        return await get_thermostat(device_id, installation)

    mock_gkp_client.get_thermostat.side_effect = fail_for_bedroom
    device_contents[LIVING_ROOM_ID]["At"]["value"] = "734"

    await _tick(hass, freezer, UPDATE_INTERVAL)

    living_room = hass.states.get(LIVING_ROOM_ENTITY_ID)
    bedroom = hass.states.get(BEDROOM_ENTITY_ID)
    assert living_room is not None
    assert living_room.attributes["current_temperature"] == 23.0
    assert bedroom is not None
    assert bedroom.state != STATE_UNAVAILABLE
    assert bedroom.attributes["current_temperature"] == 19.0


async def test_device_offline_when_not_reporting(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_contents: dict[str, dict[str, Any]],
) -> None:
    """Test a device is unavailable once its device date gets too old."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    await _tick(hass, freezer, OFFLINE_AFTER)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # A new report brings the device back
    device_contents[LIVING_ROOM_ID]["Dd"]["value"] = "30/9/2026 14:36:00"
    await _tick(hass, freezer, UPDATE_INTERVAL)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def _set_temperature(hass: HomeAssistant) -> None:
    """Send a temperature command, which starts fast polling."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, ATTR_TEMPERATURE: 23.5},
        blocking=True,
    )


async def test_device_coordinator_refresh_error(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device coordinator handles refresh error."""
    await setup_integration(hass, mock_config_entry)
    await _set_temperature(hass)
    mock_gkp_client.set_temperature.assert_called_once_with(
        LIVING_ROOM_ID, GkpMode.COMFORT, 23.5
    )

    mock_gkp_client.get_thermostat.side_effect = GkpConnectionError("lost")
    await _tick(hass, freezer, FAST_POLLING_INTERVAL)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_rate_limited(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the next update waits for the delay requested by the API."""
    await setup_integration(hass, mock_config_entry)
    await _tick(hass, freezer, USER_CONNECTED_REPORT_DELAY)
    mock_gkp_client.get_thermostat.side_effect = GkpRateLimitError("limited", 120)

    await _tick(hass, freezer, UPDATE_INTERVAL)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    mock_gkp_client.get_thermostat.reset_mock()

    await _tick(hass, freezer, timedelta(seconds=119))
    mock_gkp_client.get_thermostat.assert_not_called()

    await _tick(hass, freezer, timedelta(seconds=1))
    assert mock_gkp_client.get_thermostat.called
