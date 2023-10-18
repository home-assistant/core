"""Tests for La Marzocco switches."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.components.lamarzocco.switch import (
    ATTR_MAP_AUTO_ON_OFF,
    ATTR_MAP_MAIN_GS3_AV,
    ATTR_MAP_PREBREW_GS3_AV,
    ATTR_MAP_PREINFUSION_GS3_AV,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_main(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Main switch."""
    mock_lamarzocco.set_power.return_value = None

    state = hass.states.get("switch.GS01234_main")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Main"
    assert state.attributes.get(ATTR_ICON) == "mdi:power"
    assert state.state == STATE_ON

    # test extra attributes
    for key in ATTR_MAP_MAIN_GS3_AV:
        joined_key = str.join("_", key)
        assert state.attributes.get(joined_key) == 1023

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_main"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "switch.GS01234_main",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_power.mock_calls) == 1
    mock_lamarzocco.set_power.assert_called_once_with(enabled=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "switch.GS01234_main",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_power.mock_calls) == 2
    mock_lamarzocco.set_power.assert_called_with(enabled=True)


async def test_auto_on_off(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Auto On/Off switch."""
    mock_lamarzocco.set_auto_on_off_global.return_value = None

    state = hass.states.get("switch.GS01234_auto_on_off")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Auto On/Off"
    assert state.attributes.get(ATTR_ICON) == "mdi:alarm"
    assert state.state == STATE_ON

    # test extra attributes
    for key in ATTR_MAP_AUTO_ON_OFF:
        joined_key = str.join("_", key)
        if "auto" in joined_key:
            assert state.attributes.get(joined_key) == "Disabled"
        else:
            assert state.attributes.get(joined_key) == "00:00"

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_auto_on_off"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "switch.GS01234_auto_on_off",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off_global.mock_calls) == 1
    mock_lamarzocco.set_auto_on_off_global.assert_called_once_with(enable=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "switch.GS01234_auto_on_off",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off_global.mock_calls) == 2
    mock_lamarzocco.set_auto_on_off_global.assert_called_with(enable=True)


async def test_prebrew(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Prebrew switch."""
    mock_lamarzocco.set_prebrew.return_value = None

    state = hass.states.get("switch.GS01234_prebrew")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Prebrew"
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.state == STATE_ON

    # test extra attributes
    for key in ATTR_MAP_PREBREW_GS3_AV:
        joined_key = str.join("_", key)
        if "ton" in joined_key:
            assert state.attributes.get(joined_key) == 3
        else:
            assert state.attributes.get(joined_key) == 5

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_prebrew"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "switch.GS01234_prebrew",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_prebrew.mock_calls) == 1
    mock_lamarzocco.set_prebrew.assert_called_once_with(enabled=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "switch.GS01234_prebrew",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_prebrew.mock_calls) == 2
    mock_lamarzocco.set_prebrew.assert_called_with(enabled=True)


async def test_preinfusion(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Preinfusion switch."""
    mock_lamarzocco.set_preinfusion.return_value = None

    state = hass.states.get("switch.GS01234_preinfusion")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Preinfusion"
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.state == STATE_OFF

    # test extra attributes
    for key in ATTR_MAP_PREINFUSION_GS3_AV:
        joined_key = str.join("_", key)
        assert state.attributes.get(joined_key) == 4

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_preinfusion"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "switch.GS01234_preinfusion",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_preinfusion.mock_calls) == 1
    mock_lamarzocco.set_preinfusion.assert_called_once_with(enabled=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "switch.GS01234_preinfusion",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_preinfusion.mock_calls) == 2
    mock_lamarzocco.set_preinfusion.assert_called_with(enabled=False)


async def test_steam_boiler_enable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Steam Boiler switch."""
    mock_lamarzocco.set_steam_boiler_enable.return_value = None

    state = hass.states.get("switch.GS01234_steam_boiler_enable")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Steam Boiler Enable"
    assert state.attributes.get(ATTR_ICON) == "mdi:water-boiler"
    assert state.state == STATE_ON

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_steam_boiler_enable"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "switch.GS01234_steam_boiler_enable",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam_boiler_enable.mock_calls) == 1
    mock_lamarzocco.set_steam_boiler_enable.assert_called_once_with(enable=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "switch.GS01234_steam_boiler_enable",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam_boiler_enable.mock_calls) == 2
    mock_lamarzocco.set_steam_boiler_enable.assert_called_with(enable=True)
