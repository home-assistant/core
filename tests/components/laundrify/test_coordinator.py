"""Test the laundrify coordinator."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from laundrify_aio import exceptions

from homeassistant.components.laundrify.const import DEFAULT_POLL_INTERVAL, DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import async_fire_time_changed

# Device ID from fixtures/machines.json
DEVICE_ID = "14"


async def test_coordinator_update_success(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    laundrify_config_entry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update is performed successfully."""
    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_{SensorDeviceClass.ENERGY}"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_coordinator_update_unauthorized(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    laundrify_config_entry,
    laundrify_api_mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update fails if an UnauthorizedException is thrown."""
    laundrify_api_mock.get_machines.side_effect = exceptions.UnauthorizedException

    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_{SensorDeviceClass.ENERGY}"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_coordinator_update_connection_failed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    laundrify_config_entry,
    laundrify_api_mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update fails if an ApiConnectionException is thrown."""
    laundrify_api_mock.get_machines.side_effect = exceptions.ApiConnectionException

    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_{SensorDeviceClass.ENERGY}"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
