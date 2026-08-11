"""Tests for Daikin binary sensors."""

from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import ZoneDevice

from tests.common import MockConfigEntry

HOST = "127.0.0.1"


async def _async_setup_daikin(
    hass: HomeAssistant, zone_device: ZoneDevice
) -> MockConfigEntry:
    """Set up a Daikin config entry with a mocked library device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=zone_device.mac,
        data={CONF_HOST: HOST, KEY_MAC: zone_device.mac},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_demand_control_sensor_not_created_unsupported(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, zone_device: ZoneDevice
) -> None:
    """Test the demand control sensor is not created on unsupported devices."""
    zone_device.support_demand_control = False

    await _async_setup_daikin(hass, zone_device)

    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{zone_device.mac}-demand_control"
    )
    assert entity_id is None


async def test_demand_control_sensor_on(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, zone_device: ZoneDevice
) -> None:
    """Test the demand control sensor state when demand control is on."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control = MagicMock(
        return_value={
            "en_demand": "1",
            "mode": "0",
            "max_pow": "50",
            "scdl_per_day": "4",
        }
    )

    await _async_setup_daikin(hass, zone_device)

    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{zone_device.mac}-demand_control"
    )
    assert entity_id is not None

    await async_update_entity(hass, entity_id)
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes["mode"] == "0"
    assert state.attributes["max_pow"] == "50"
    assert state.attributes["scdl_per_day"] == "4"


async def test_demand_control_sensor_off(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, zone_device: ZoneDevice
) -> None:
    """Test the demand control sensor state when demand control is off."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control = MagicMock(
        return_value={"en_demand": "0", "mode": "0", "max_pow": "100"}
    )

    await _async_setup_daikin(hass, zone_device)

    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{zone_device.mac}-demand_control"
    )
    assert entity_id is not None

    await async_update_entity(hass, entity_id)
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes["max_pow"] == "100"
