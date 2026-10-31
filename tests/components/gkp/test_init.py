"""Test the GKP integration initialization."""

from collections.abc import Callable, Iterable
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from gkphomepython import (
    USER_CONNECTED_INTERVAL,
    USER_CONNECTED_REPORT_DELAY,
    GkpAuthError,
    GkpConnectionError,
    GkpDeviceError,
    GkpError,
    GkpRateLimitError,
    Installation,
    ThermostatsResult,
)
from gkphomepython.const import FIRST_REPORT_TIMEOUT, OFFLINE_AFTER
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.gkp.const import (
    DISCOVERY_INTERVAL,
    DOMAIN,
    FAST_POLLING_INTERVAL,
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import advance_time, setup_integration
from .conftest import (
    BEDROOM_ENTITY_ID,
    BEDROOM_ID,
    LIVING_ROOM_ENTITY_ID,
    LIVING_ROOM_ID,
)

RETRY_AFTER = 120


def _all_devices_failing(installations: Iterable[Installation]) -> ThermostatsResult:
    """Return a result where no device could be read."""
    return ThermostatsResult(
        errors={
            device_id: GkpConnectionError("lost")
            for installation in installations
            for device_id in installation.device_ids
        }
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
    mock_gkp_client.get_thermostats.assert_called_once()

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
    ("exception", "expected_state"),
    [
        pytest.param(
            GkpAuthError("Auth failed"), ConfigEntryState.SETUP_ERROR, id="auth_error"
        ),
        pytest.param(
            GkpConnectionError("Connection lost"),
            ConfigEntryState.SETUP_RETRY,
            id="connection_error",
        ),
        pytest.param(
            GkpError("API error"), ConfigEntryState.SETUP_RETRY, id="api_error"
        ),
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
    mock_gkp_client.get_thermostats.side_effect = _all_devices_failing

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
    assert not hass.states.async_entity_ids()


async def test_wake_up_interval(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test devices are woken up every wake up interval only."""
    await setup_integration(hass, mock_config_entry)
    assert mock_gkp_client.notify_user_connected.call_count == 1

    await advance_time(hass, freezer, USER_CONNECTED_INTERVAL - UPDATE_INTERVAL)
    assert mock_gkp_client.notify_user_connected.call_count == 1

    await advance_time(hass, freezer, UPDATE_INTERVAL)
    assert mock_gkp_client.notify_user_connected.call_count == 2


async def test_refresh_after_wake_up(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the devices are read again shortly after being woken up."""
    await setup_integration(hass, mock_config_entry)
    assert mock_gkp_client.get_thermostats.call_count == 1

    await advance_time(hass, freezer, USER_CONNECTED_REPORT_DELAY)
    assert mock_gkp_client.get_thermostats.call_count == 2

    # Back to the regular interval once the answer was read
    await advance_time(hass, freezer, USER_CONNECTED_REPORT_DELAY)
    assert mock_gkp_client.get_thermostats.call_count == 2


@pytest.mark.usefixtures("mock_gkp_client")
async def test_available_until_first_report_timeout(
    hass: HomeAssistant,
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

    await advance_time(hass, freezer, FIRST_REPORT_TIMEOUT)
    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Later wake ups do not make a silent device available again
    await advance_time(hass, freezer, USER_CONNECTED_INTERVAL)
    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    device_contents[LIVING_ROOM_ID]["Dd"]["value"] = "30/9/2026 14:18:00"
    await advance_time(hass, freezer, USER_CONNECTED_REPORT_DELAY)
    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("exception", "has_reauth_flow"),
    [
        pytest.param(GkpAuthError("expired"), True, id="auth_error"),
        pytest.param(GkpConnectionError("lost"), False, id="connection_error"),
    ],
)
async def test_wake_up_errors(
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
    mock_gkp_client.get_thermostats.reset_mock()

    await advance_time(hass, freezer, USER_CONNECTED_INTERVAL)

    assert (
        any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        == has_reauth_flow
    )
    # A failed wake up does not prevent reading the devices
    assert mock_gkp_client.get_thermostats.called is not has_reauth_flow


@pytest.mark.usefixtures("mock_gkp_client")
async def test_dynamic_device_creation(
    hass: HomeAssistant,
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

    await advance_time(hass, freezer, DISCOVERY_INTERVAL)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "AABBCCDDEE03"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Kitchen"
    assert hass.states.get("climate.kitchen") is not None


@pytest.mark.usefixtures("mock_gkp_client")
async def test_stale_device_removal(
    hass: HomeAssistant,
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

    await advance_time(hass, freezer, DISCOVERY_INTERVAL)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, BEDROOM_ID), mock_config_entry.entry_id
        )
        is None
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, LIVING_ROOM_ID), mock_config_entry.entry_id
    )


@pytest.mark.usefixtures("mock_gkp_client")
async def test_stale_device_removal_on_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test devices removed while Home Assistant was stopped are removed."""
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "AABBCCDDEE03")},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "AABBCCDDEE03"), mock_config_entry.entry_id
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

    await advance_time(hass, freezer, DISCOVERY_INTERVAL)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, BEDROOM_ID), mock_config_entry.entry_id
    )
    state = hass.states.get(BEDROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("side_effect", "has_reauth_flow"),
    [
        pytest.param(GkpAuthError("expired"), True, id="auth_error"),
        pytest.param(_all_devices_failing, False, id="all_devices_failing"),
    ],
)
async def test_update_errors(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception | Callable[[Iterable[Installation]], ThermostatsResult],
    has_reauth_flow: bool,
) -> None:
    """Test errors during a regular update make the entities unavailable."""
    await setup_integration(hass, mock_config_entry)
    mock_gkp_client.get_thermostats.side_effect = side_effect

    await advance_time(hass, freezer, UPDATE_INTERVAL)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
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
    get_thermostats = mock_gkp_client.get_thermostats.side_effect

    async def fail_for_bedroom(
        installations: Iterable[Installation],
    ) -> ThermostatsResult:
        result = await get_thermostats(installations)
        del result.thermostats[BEDROOM_ID]
        result.errors[BEDROOM_ID] = GkpDeviceError("not found")
        return result

    mock_gkp_client.get_thermostats.side_effect = fail_for_bedroom
    device_contents[LIVING_ROOM_ID]["At"]["value"] = "734"

    await advance_time(hass, freezer, UPDATE_INTERVAL)

    living_room = hass.states.get(LIVING_ROOM_ENTITY_ID)
    bedroom = hass.states.get(BEDROOM_ENTITY_ID)
    assert living_room is not None
    assert living_room.attributes["current_temperature"] == 23.0
    assert bedroom is not None
    assert bedroom.state != STATE_UNAVAILABLE
    assert bedroom.attributes["current_temperature"] == 19.0


@pytest.mark.usefixtures("mock_gkp_client")
async def test_device_offline_when_not_reporting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_contents: dict[str, dict[str, Any]],
) -> None:
    """Test a device is unavailable once its device date gets too old."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    await advance_time(hass, freezer, OFFLINE_AFTER)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # A new report brings the device back
    device_contents[LIVING_ROOM_ID]["Dd"]["value"] = "30/9/2026 14:36:00"
    await advance_time(hass, freezer, UPDATE_INTERVAL)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("exception", "has_reauth_flow"),
    [
        pytest.param(GkpConnectionError("lost"), False, id="connection_error"),
        pytest.param(GkpAuthError("expired"), True, id="auth_error"),
    ],
)
async def test_refresh_after_command_error(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
    has_reauth_flow: bool,
) -> None:
    """Test a device is unavailable when it cannot be read after a command."""
    await setup_integration(hass, mock_config_entry)
    # A command starts fast polling of the device
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, ATTR_TEMPERATURE: 23.5},
        blocking=True,
    )

    mock_gkp_client.get_thermostat.side_effect = exception
    await advance_time(hass, freezer, FAST_POLLING_INTERVAL)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert (
        any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        == has_reauth_flow
    )


async def test_rate_limited(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the next update waits for the delay requested by the API."""
    await setup_integration(hass, mock_config_entry)
    await advance_time(hass, freezer, USER_CONNECTED_REPORT_DELAY)
    get_thermostats = mock_gkp_client.get_thermostats.side_effect
    mock_gkp_client.get_thermostats.side_effect = GkpRateLimitError(
        "limited", RETRY_AFTER
    )

    await advance_time(hass, freezer, UPDATE_INTERVAL)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    mock_gkp_client.get_thermostats.reset_mock()

    await advance_time(hass, freezer, timedelta(seconds=RETRY_AFTER - 1))
    mock_gkp_client.get_thermostats.assert_not_called()

    mock_gkp_client.get_thermostats.side_effect = get_thermostats
    await advance_time(hass, freezer, timedelta(seconds=1))
    assert mock_gkp_client.get_thermostats.called

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_setup_entry_rate_limited(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the setup is retried after the delay requested by the API."""
    get_installations = mock_gkp_client.get_installations.side_effect
    mock_gkp_client.get_installations.side_effect = GkpRateLimitError(
        "limited", RETRY_AFTER
    )

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_gkp_client.get_installations.side_effect = get_installations
    await advance_time(hass, freezer, timedelta(seconds=RETRY_AFTER - 1))
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    await advance_time(hass, freezer, timedelta(seconds=1))
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("method", "interval"),
    [
        pytest.param("get_installations", DISCOVERY_INTERVAL, id="discovery"),
        pytest.param("notify_user_connected", USER_CONNECTED_INTERVAL, id="wake_up"),
    ],
)
async def test_rate_limited_before_fetching_thermostats(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
    interval: timedelta,
) -> None:
    """Test a rate limit stops the hub update until the requested delay."""
    await setup_integration(hass, mock_config_entry)
    rate_limited_method = getattr(mock_gkp_client, method)
    rate_limited_method.side_effect = GkpRateLimitError("limited", RETRY_AFTER)
    mock_gkp_client.get_thermostats.reset_mock()

    await advance_time(hass, freezer, interval)

    mock_gkp_client.get_thermostats.assert_not_called()
    rate_limited_method.reset_mock()

    await advance_time(hass, freezer, timedelta(seconds=RETRY_AFTER - 1))
    rate_limited_method.assert_not_called()

    await advance_time(hass, freezer, timedelta(seconds=1))
    assert rate_limited_method.called


async def test_refresh_after_command_rate_limited(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test fast polling waits for the delay requested by the API."""
    await setup_integration(hass, mock_config_entry)
    mock_gkp_client.get_thermostat.side_effect = GkpRateLimitError(
        "limited", RETRY_AFTER
    )

    # A command starts fast polling of the device
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, ATTR_TEMPERATURE: 23.5},
        blocking=True,
    )
    mock_gkp_client.get_thermostat.assert_called_once()
    mock_gkp_client.get_thermostat.reset_mock()

    await advance_time(hass, freezer, timedelta(seconds=RETRY_AFTER - 1))
    mock_gkp_client.get_thermostat.assert_not_called()

    await advance_time(hass, freezer, timedelta(seconds=1))
    assert mock_gkp_client.get_thermostat.called
