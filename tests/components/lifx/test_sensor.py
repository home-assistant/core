"""Tests for the lifx integration sensor platform."""

from homeassistant.components import lifx
from homeassistant.components.lifx import DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    SIGNAL_STRENGTH_DECIBELS,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import (
    IP_ADDRESS,
    MAC_ADDRESS,
    MockFailingLifxCommand,
    _mocked_bulb,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry


async def test_rssi_and_uptime_sensors(hass: HomeAssistant) -> None:
    """Test the RSSI sensor on a LIFX bulb."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_ids = ["sensor.my_bulb_rssi", "sensor.my_bulb_uptime"]

    entity_registry = er.async_get(hass)
    registry_entries = [
        entity_registry.entities.get(entity_id) for entity_id in entity_ids
    ]
    assert [not registry_entry.disabled for registry_entry in registry_entries]

    states = [hass.states.get(entity_id) for entity_id in entity_ids]
    assert states[0].state == "16"
    assert states[1].state == "609815"
    assert (
        states[0].attributes.get(ATTR_UNIT_OF_MEASUREMENT) == SIGNAL_STRENGTH_DECIBELS
    )
    assert states[1].attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TIME_SECONDS


async def test_failing_sensors(hass: HomeAssistant) -> None:
    """Test the RSSI sensor on a LIFX bulb."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()

    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    bulb.get_hostinfo = MockFailingLifxCommand(bulb)
    bulb.get_wifiinfo = MockFailingLifxCommand(bulb)
