"""Tests for the srp_energy sensor platform."""
from homeassistant.components.srp_energy.const import (
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    ENERGY_KWH,
    ICON,
    SENSOR_NAME,
    SENSOR_TYPE,
)
from homeassistant.components.srp_energy.sensor import SrpEntity, async_setup_entry
from homeassistant.const import ATTR_ATTRIBUTION

from tests.async_mock import MagicMock


async def test_async_setup_entry(hass):
    """Test the sensor."""
    fake_async_add_entities = MagicMock()
    fake_srp_engery_client = MagicMock()
    config = {}
    hass.data[DOMAIN] = fake_srp_engery_client

    await async_setup_entry(hass, config, fake_async_add_entities)
    assert fake_async_add_entities.called
    assert fake_srp_engery_client.usage.called


async def test_srp_entity(hass):
    """Test the SrpEntity."""
    fake_coordinator = MagicMock()
    srp_entity = SrpEntity(fake_coordinator)

    assert srp_entity is not None
    assert srp_entity.name == f"{DEFAULT_NAME} {SENSOR_NAME}"
    assert srp_entity.unique_id == SENSOR_TYPE
    assert srp_entity.state is None
    assert srp_entity.unit_of_measurement == ENERGY_KWH
    assert srp_entity.icon == ICON
    assert srp_entity.usage is not None
    assert srp_entity.should_poll is False
    assert srp_entity.device_state_attributes[ATTR_ATTRIBUTION] == ATTRIBUTION
    assert srp_entity.available is not None

    await srp_entity.async_added_to_hass()
    assert srp_entity.state is not None
    assert fake_coordinator.async_add_listener.called
    assert not fake_coordinator.async_add_listener.data.called
