"""Tests for the Daikin switch platform."""

from __future__ import annotations

from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.components.daikin.switch import DAIKIN_ATTR_MODE
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ZoneDevice, configure_zone_device

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


def _zone_entity_id(
    entity_registry: er.EntityRegistry, zone_device: ZoneDevice, zone_id: int
) -> str | None:
    """Return the entity id for a zone climate unique id."""
    return entity_registry.async_get_entity_id(
        SWITCH_DOMAIN,
        DOMAIN,
        f"{zone_device.mac}-toggle",
    )


async def test_device_state_off(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, zone_device: ZoneDevice
) -> None:
    """Setting a switch should update the state of the device."""
    # Arrange
    configure_zone_device(zone_device, zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None
    assert zone_device._mode != "off"

    # Act
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )

    # Assert
    zone_device.set.assert_awaited_once_with({DAIKIN_ATTR_MODE: "off"})
    assert zone_device._mode == "off"
    assert hass.states.get(entity_id).state == "off"


async def test_device_state_on(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, zone_device: ZoneDevice
) -> None:
    """Setting a switch should update the state of the device."""
    # Arrange
    configure_zone_device(zone_device, zones=[["Living", "1", 22]], mode="off")
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None
    assert zone_device._mode == "off"

    # Act
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )

    # Assert
    zone_device.set.assert_awaited_once_with({DAIKIN_ATTR_MODE: "on"})
    assert zone_device._mode == "on"
    assert hass.states.get(entity_id).state == "on"
