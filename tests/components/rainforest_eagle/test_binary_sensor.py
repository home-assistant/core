"""Tests for Rainforest Eagle meter connectivity."""

from datetime import timedelta
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.rainforest_eagle.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

ENTITY_ID = "binary_sensor.eagle_200_meter_connectivity"


async def _refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance to the next coordinator poll."""
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_meter_connectivity(
    hass: HomeAssistant,
    setup_rainforest_200: Mock,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test meter disconnects and reconnects on the gateway's device."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY

    entry = entity_registry.async_get(ENTITY_ID)
    power_entry = entity_registry.async_get("sensor.eagle_200_power_demand")
    assert entry.device_id == power_entry.device_id
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert device_registry.async_get(entry.device_id).identifiers == {(DOMAIN, "12345")}

    setup_rainforest_200.is_connected = False
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert hass.states.get("sensor.eagle_200_power_demand").state == STATE_UNAVAILABLE

    setup_rainforest_200.is_connected = True
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert hass.states.get("sensor.eagle_200_power_demand").state == "1.152000"


async def test_gateway_unavailable(
    hass: HomeAssistant,
    setup_rainforest_200: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed gateway request is not reported as a meter disconnect."""
    setup_rainforest_200.get_device_query.side_effect = TimeoutError
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    setup_rainforest_200.get_device_query.side_effect = None
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("setup_rainforest_100")
async def test_legacy_gateway(hass: HomeAssistant) -> None:
    """Do not report connectivity for gateways without meter link status."""
    assert not hass.states.async_all("binary_sensor")


async def test_initially_disconnected(
    hass: HomeAssistant, setup_rainforest_200: Mock
) -> None:
    """Test setup while the meter is disconnected and integration unloading."""
    setup_rainforest_200.is_connected = False
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
