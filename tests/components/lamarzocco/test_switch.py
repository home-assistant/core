"""Tests for La Marzocco switches."""
from unittest.mock import MagicMock

from lmcloud.const import LaMarzoccoModel
import pytest

from homeassistant.components.lamarzocco.const import DOMAIN
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
    serial_number = mock_lamarzocco.serial_number

    mock_lamarzocco.set_power.return_value = None

    state = hass.states.get(f"switch.{serial_number}_main")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == f"{serial_number} Main"
    assert state.attributes.get(ATTR_ICON) == "mdi:power"
    assert state.state == STATE_ON

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == f"{serial_number}_main"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, serial_number)}
    assert device.manufacturer == "La Marzocco"
    assert device.name == serial_number
    assert device.serial_number == serial_number
    assert device.sw_version == "1.1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_main",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_power.mock_calls) == 1
    mock_lamarzocco.set_power.assert_called_once_with(enabled=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_main",
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
    serial_number = mock_lamarzocco.serial_number
    mock_lamarzocco.set_auto_on_off_global.return_value = None

    state = hass.states.get(f"switch.{serial_number}_auto_on_off")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == f"{serial_number} Auto on/off"
    assert state.attributes.get(ATTR_ICON) == "mdi:alarm"
    assert state.state == STATE_ON

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == f"{serial_number}_auto_on_off"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, serial_number)}
    assert device.manufacturer == "La Marzocco"
    assert device.name == serial_number
    assert device.serial_number == serial_number
    assert device.sw_version == "1.1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_auto_on_off",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off_global.mock_calls) == 1
    mock_lamarzocco.set_auto_on_off_global.assert_called_once_with(enable=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_auto_on_off",
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
    serial_number = mock_lamarzocco.serial_number
    mock_lamarzocco.set_prebrew.return_value = None

    state = hass.states.get(f"switch.{serial_number}_prebrew")

    if mock_lamarzocco.model_name == LaMarzoccoModel.GS3_MP:
        assert state is None
        return
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == f"{serial_number} Prebrew"
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.state == STATE_ON

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == f"{serial_number}_prebrew"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, serial_number)}
    assert device.manufacturer == "La Marzocco"
    assert device.name == serial_number
    assert device.serial_number == serial_number
    assert device.sw_version == "1.1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_prebrew",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_prebrew.mock_calls) == 1
    mock_lamarzocco.set_prebrew.assert_called_once_with(enabled=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_prebrew",
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
    serial_number = mock_lamarzocco.serial_number
    mock_lamarzocco.set_preinfusion.return_value = None

    state = hass.states.get(f"switch.{serial_number}_preinfusion")

    if mock_lamarzocco.model_name == LaMarzoccoModel.GS3_MP:
        assert state is None
        return

    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == f"{serial_number} Preinfusion"
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == f"{serial_number}_preinfusion"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, serial_number)}
    assert device.manufacturer == "La Marzocco"
    assert device.name == serial_number
    assert device.serial_number == serial_number
    assert device.sw_version == "1.1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_preinfusion",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_preinfusion.mock_calls) == 1
    mock_lamarzocco.set_preinfusion.assert_called_once_with(enabled=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_preinfusion",
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
    serial_number = mock_lamarzocco.serial_number
    mock_lamarzocco.set_steam_boiler_enable.return_value = None

    state = hass.states.get(f"switch.{serial_number}_steam_boiler")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == f"{serial_number} Steam boiler"
    assert state.attributes.get(ATTR_ICON) == "mdi:water-boiler"
    assert state.state == STATE_ON

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == f"{serial_number}_steam_boiler_enable"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, serial_number)}
    assert device.manufacturer == "La Marzocco"
    assert device.name == serial_number
    assert device.serial_number == serial_number
    assert device.sw_version == "1.1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_steam_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam_boiler_enable.mock_calls) == 1
    mock_lamarzocco.set_steam_boiler_enable.assert_called_once_with(enable=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_steam_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam_boiler_enable.mock_calls) == 2
    mock_lamarzocco.set_steam_boiler_enable.assert_called_with(enable=True)
