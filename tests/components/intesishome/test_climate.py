"""Tests for the IntesisHome climate platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyintesishome import IHConnectionError
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import PLATFORM_NOT_READY_BASE_WAIT_TIME
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed

ENTITY_ID = "climate.office"


@pytest.fixture
def mock_controller() -> Generator[MagicMock]:
    """Mock the pyintesishome controller."""
    with patch(
        "homeassistant.components.intesishome.climate.IntesisHome", autospec=True
    ) as intesis_home:
        controller = intesis_home.return_value
        controller.device_type = "IntesisHome"
        controller.get_devices.return_value = {"device-id": {"name": "Office"}}
        controller.has_setpoint_control.return_value = False
        controller.has_vertical_swing.return_value = False
        controller.has_horizontal_swing.return_value = False
        controller.get_fan_speed_list.return_value = []
        controller.get_mode_list.return_value = []
        controller.add_update_callback = MagicMock()
        controller.remove_update_callback = MagicMock()
        controller.is_available = True
        controller.get_temperature.return_value = 22
        controller.get_fan_speed.return_value = None
        controller.is_on.return_value = False
        controller.get_min_setpoint.return_value = 16
        controller.get_max_setpoint.return_value = 30
        controller.get_rssi.return_value = None
        controller.get_run_hours.return_value = None
        controller.get_setpoint.return_value = 21
        controller.get_outdoor_temperature.return_value = None
        controller.get_mode.return_value = "cool"
        controller.get_preset_mode.return_value = None
        controller.get_vertical_swing.return_value = "auto/stop"
        controller.get_horizontal_swing.return_value = "auto/stop"
        controller.get_heat_power_consumption.return_value = None
        controller.get_cool_power_consumption.return_value = None
        yield controller


async def setup_platform(hass: HomeAssistant) -> None:
    """Set up the IntesisHome climate platform."""
    assert await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: {
                CONF_PLATFORM: "intesishome",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "password",
            }
        },
    )
    await hass.async_block_till_done()


async def test_setup_platform_registers_callback(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test registering the synchronous library update callback during setup."""
    await setup_platform(hass)

    assert hass.states.get(ENTITY_ID) is not None
    mock_controller.add_update_callback.assert_called_once()
    assert callable(mock_controller.add_update_callback.call_args.args[0])
    mock_controller.connect.assert_awaited_once_with()


async def test_availability_follows_controller(
    hass: HomeAssistant, mock_controller: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test polling picks up availability changes with no library callback."""
    await setup_platform(hass)
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    # Availability follows how long since the controller's poller last got
    # through, so nothing calls back to announce either transition.
    mock_controller.is_available = False
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_controller.is_available = True
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    # Recovered without reconnecting: connect() was only called during setup.
    assert mock_controller.connect.await_count == 1


async def test_setup_platform_retries_on_connection_error(
    hass: HomeAssistant, mock_controller: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test an unreachable API leaves the platform to be set up again later."""
    mock_controller.connect.side_effect = IHConnectionError

    await setup_platform(hass)
    assert hass.states.get(ENTITY_ID) is None

    mock_controller.connect.side_effect = None
    freezer.tick(timedelta(seconds=PLATFORM_NOT_READY_BASE_WAIT_TIME))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is not None


async def test_removing_one_entity_keeps_controller_running(
    hass: HomeAssistant,
    mock_controller: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the shared controller outlives the removal of a single entity."""
    mock_controller.get_devices.return_value = {
        "device-id": {"name": "Office"},
        "other-device-id": {"name": "Lounge"},
    }
    await setup_platform(hass)

    registered_callbacks = [
        call.args[0] for call in mock_controller.add_update_callback.call_args_list
    ]
    assert len(registered_callbacks) == 2

    entity_registry.async_remove(ENTITY_ID)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is None
    mock_controller.stop.assert_not_awaited()
    assert hass.states.get("climate.lounge").state != STATE_UNAVAILABLE

    # Only the removed entity detaches; the other keeps receiving updates.
    removed_callbacks = [
        call.args[0] for call in mock_controller.remove_update_callback.call_args_list
    ]
    assert len(removed_callbacks) == 1
    assert removed_callbacks[0] in registered_callbacks
