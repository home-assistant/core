"""Tests for the srp_energy sensor platform."""
from unittest.mock import MagicMock

from homeassistant.components.srp_energy.const import (
    ATTRIBUTION,
    DEFAULT_NAME,
    ICON,
    SENSOR_NAME,
    SENSOR_TYPE,
    SRP_ENERGY_DOMAIN,
)
from homeassistant.components.srp_energy.sensor import SrpEntity, async_setup_entry
from homeassistant.const import ATTR_ATTRIBUTION, ENERGY_KILO_WATT_HOUR


async def test_async_setup_entry(hass):
    """Test the sensor."""
    fake_async_add_entities = MagicMock()
    fake_srp_energy_client = MagicMock()
    fake_srp_energy_client.usage.return_value = [{1, 2, 3, 1.999, 4}]
    fake_config = MagicMock(
        data={
            "name": "SRP Energy",
            "is_tou": False,
            "id": "0123456789",
            "username": "testuser@example.com",
            "password": "mypassword",
        }
    )
    hass.data[SRP_ENERGY_DOMAIN] = fake_srp_energy_client

    await async_setup_entry(hass, fake_config, fake_async_add_entities)


async def test_async_setup_entry_timeout_error(hass):
    """Test fetching usage data. Failed the first time because was too get response."""
    fake_async_add_entities = MagicMock()
    fake_srp_energy_client = MagicMock()
    fake_srp_energy_client.usage.return_value = [{1, 2, 3, 1.999, 4}]
    fake_config = MagicMock(
        data={
            "name": "SRP Energy",
            "is_tou": False,
            "id": "0123456789",
            "username": "testuser@example.com",
            "password": "mypassword",
        }
    )
    hass.data[SRP_ENERGY_DOMAIN] = fake_srp_energy_client
    fake_srp_energy_client.usage.side_effect = TimeoutError()

    await async_setup_entry(hass, fake_config, fake_async_add_entities)
    assert not fake_async_add_entities.call_args[0][0][
        0
    ].coordinator.last_update_success


async def test_async_setup_entry_connect_error(hass):
    """Test fetching usage data. Failed the first time because was too get response."""
    fake_async_add_entities = MagicMock()
    fake_srp_energy_client = MagicMock()
    fake_srp_energy_client.usage.return_value = [{1, 2, 3, 1.999, 4}]
    fake_config = MagicMock(
        data={
            "name": "SRP Energy",
            "is_tou": False,
            "id": "0123456789",
            "username": "testuser@example.com",
            "password": "mypassword",
        }
    )
    hass.data[SRP_ENERGY_DOMAIN] = fake_srp_energy_client
    fake_srp_energy_client.usage.side_effect = ValueError()

    await async_setup_entry(hass, fake_config, fake_async_add_entities)
    assert not fake_async_add_entities.call_args[0][0][
        0
    ].coordinator.last_update_success


async def test_srp_entity(hass):
    """Test the SrpEntity."""
    fake_coordinator = MagicMock(data=1.99999999999)
    srp_entity = SrpEntity(fake_coordinator)

    assert srp_entity is not None
    assert srp_entity.name == f"{DEFAULT_NAME} {SENSOR_NAME}"
    assert srp_entity.unique_id == SENSOR_TYPE
    assert srp_entity.state is None
    assert srp_entity.unit_of_measurement == ENERGY_KILO_WATT_HOUR
    assert srp_entity.icon == ICON
    assert srp_entity.usage == "2.00"
    assert srp_entity.should_poll is False
    assert srp_entity.extra_state_attributes[ATTR_ATTRIBUTION] == ATTRIBUTION
    assert srp_entity.available is not None

    await srp_entity.async_added_to_hass()
    assert srp_entity.state is not None
    assert fake_coordinator.async_add_listener.called
    assert not fake_coordinator.async_add_listener.data.called


async def test_srp_entity_no_data(hass):
    """Test the SrpEntity."""
    fake_coordinator = MagicMock(data=False)
    srp_entity = SrpEntity(fake_coordinator)
    assert srp_entity.extra_state_attributes is None


async def test_srp_entity_no_coord_data(hass):
    """Test the SrpEntity."""
    fake_coordinator = MagicMock(data=False)
    srp_entity = SrpEntity(fake_coordinator)

    assert srp_entity.usage is None


async def test_srp_entity_async_update(hass):
    """Test the SrpEntity."""

    async def async_magic():
        pass

    MagicMock.__await__ = lambda x: async_magic().__await__()
    fake_coordinator = MagicMock(data=False)
    srp_entity = SrpEntity(fake_coordinator)

    await srp_entity.async_update()
    assert fake_coordinator.async_request_refresh.called
