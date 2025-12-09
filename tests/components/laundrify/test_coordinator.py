"""Test the laundrify coordinator."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from laundrify_aio import LaundrifyDevice, exceptions

from homeassistant.components.laundrify.const import DEFAULT_POLL_INTERVAL, DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from tests.common import async_fire_time_changed


def get_coord_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: LaundrifyDevice,
) -> State | None:
    """Get the coordinated energy sensor entity."""
    unique_id = f"{mock_device.id}_{SensorDeviceClass.ENERGY}"
    entity_entry = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    if entity_entry is None:
        return None
    return hass.states.get(entity_entry)


async def test_coordinator_update_success(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    laundrify_config_entry,
    mock_device: LaundrifyDevice,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update is performed successfully."""
    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coord_entity = get_coord_entity(hass, entity_registry, mock_device)
    assert coord_entity is not None
    assert coord_entity.state != STATE_UNAVAILABLE


async def test_coordinator_update_unauthorized(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    laundrify_config_entry,
    laundrify_api_mock,
    mock_device: LaundrifyDevice,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update fails if an UnauthorizedException is thrown."""
    laundrify_api_mock.get_machines.side_effect = exceptions.UnauthorizedException

    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coord_entity = get_coord_entity(hass, entity_registry, mock_device)
    assert coord_entity is not None
    assert coord_entity.state == STATE_UNAVAILABLE


async def test_coordinator_update_connection_failed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    laundrify_config_entry,
    laundrify_api_mock,
    mock_device: LaundrifyDevice,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update fails if an ApiConnectionException is thrown."""
    laundrify_api_mock.get_machines.side_effect = exceptions.ApiConnectionException

    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coord_entity = get_coord_entity(hass, entity_registry, mock_device)
    assert coord_entity is not None
    assert coord_entity.state == STATE_UNAVAILABLE
