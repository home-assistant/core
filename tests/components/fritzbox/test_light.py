"""Tests for AVM Fritz!Box light component."""

from datetime import timedelta
from unittest.mock import Mock, call, patch

from requests.exceptions import HTTPError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fritzbox.const import COLOR_MODE, COLOR_TEMP_MODE, DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import FritzDeviceLightMock, set_devices, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed, snapshot_platform

ENTITY_ID = f"{LIGHT_DOMAIN}.{CONF_FAKE_NAME}"


async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fritz: Mock,
) -> None:
    """Test setup of platform."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    device.color_mode = COLOR_TEMP_MODE
    device.color_temp = 2700

    with patch("homeassistant.components.fritzbox.PLATFORMS", [Platform.LIGHT]):
        entry = await setup_config_entry(
            hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
        )
    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_setup_non_color(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fritz: Mock,
) -> None:
    """Test setup of platform of non color bulb."""
    device = FritzDeviceLightMock()
    device.has_color = False
    device.get_color_temps.return_value = []
    device.get_colors.return_value = {}

    with patch("homeassistant.components.fritzbox.PLATFORMS", [Platform.LIGHT]):
        entry = await setup_config_entry(
            hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
        )
    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_setup_non_color_non_level(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fritz: Mock,
) -> None:
    """Test setup of platform of non color and non level bulb."""
    device = FritzDeviceLightMock()
    device.has_color = False
    device.has_level = False
    device.get_color_temps.return_value = []
    device.get_colors.return_value = {}

    with patch("homeassistant.components.fritzbox.PLATFORMS", [Platform.LIGHT]):
        entry = await setup_config_entry(
            hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
        )
    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_setup_color(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fritz: Mock,
) -> None:
    """Test setup of platform in color mode."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    device.color_mode = COLOR_MODE
    device.hue = 100
    device.saturation = 70 * 255.0 / 100.0

    with patch("homeassistant.components.fritzbox.PLATFORMS", [Platform.LIGHT]):
        entry = await setup_config_entry(
            hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
        )
    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_turn_on(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn device on."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    assert await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 100, ATTR_COLOR_TEMP_KELVIN: 3000},
        True,
    )
    assert device.set_state_on.call_count == 1
    assert device.set_level.call_count == 1
    assert device.set_color_temp.call_count == 1
    assert device.set_color_temp.call_args_list == [call(3000, 0, True)]
    assert device.set_level.call_args_list == [call(100, True)]


async def test_turn_on_color(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn device on in color mode."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    device.fullcolorsupport = True
    assert await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 100, ATTR_HS_COLOR: (100, 70)},
        True,
    )
    assert device.set_state_on.call_count == 1
    assert device.set_level.call_count == 1
    assert device.set_unmapped_color.call_count == 1
    assert device.set_color.call_count == 0
    assert device.set_level.call_args_list == [call(100, True)]
    assert device.set_unmapped_color.call_args_list == [
        call((100, round(70 * 255.0 / 100.0)), 0, True)
    ]


async def test_turn_on_color_no_fullcolorsupport(
    hass: HomeAssistant, fritz: Mock
) -> None:
    """Test turn device on in mapped color mode if unmapped is not supported."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    device.fullcolorsupport = False
    assert await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 100, ATTR_HS_COLOR: (100, 70)},
        True,
    )
    assert device.set_state_on.call_count == 1
    assert device.set_level.call_count == 1
    assert device.set_color.call_count == 1
    assert device.set_unmapped_color.call_count == 0
    assert device.set_level.call_args_list == [call(100, True)]
    assert device.set_color.call_args_list == [call((100, 70), 0, True)]


async def test_turn_off(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn device off."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    assert await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_state_off.call_count == 1


async def test_update(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update without error."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    assert await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert fritz().update_devices.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert fritz().update_devices.call_count == 2
    assert fritz().login.call_count == 1


async def test_update_error(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update with error."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    fritz().update_devices.side_effect = HTTPError("Boom")
    entry = await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert fritz().update_devices.call_count == 2
    assert fritz().login.call_count == 2

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert fritz().update_devices.call_count == 4
    assert fritz().login.call_count == 4


async def test_discover_new_device(hass: HomeAssistant, fritz: Mock) -> None:
    """Test adding new discovered devices during runtime."""
    device = FritzDeviceLightMock()
    device.get_color_temps.return_value = [2700, 6500]
    device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    device.color_mode = COLOR_TEMP_MODE
    device.color_temp = 2700
    assert await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state

    new_device = FritzDeviceLightMock()
    new_device.ain = "7890 1234"
    new_device.name = "new_light"
    new_device.get_color_temps.return_value = [2700, 6500]
    new_device.get_colors.return_value = {
        "Red": [("100", "70", "10"), ("100", "50", "10"), ("100", "30", "10")]
    }
    new_device.color_mode = COLOR_TEMP_MODE
    new_device.color_temp = 2700
    set_devices(fritz, devices=[device, new_device])

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{LIGHT_DOMAIN}.new_light")
    assert state
