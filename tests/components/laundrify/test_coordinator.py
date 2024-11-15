"""Test the laundrify coordinator."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from laundrify_aio import LaundrifyDevice, exceptions

from homeassistant.components.laundrify.const import DEFAULT_POLL_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.util import slugify

from tests.common import async_fire_time_changed


def get_coord_entity(hass: HomeAssistant, mock_device: LaundrifyDevice) -> State:
    """Get the coordinated energy sensor entity."""
    device_slug = slugify(mock_device.name, separator="_")
    return hass.states.get(f"sensor.{device_slug}_energy")


async def test_coordinator_update_success(
    hass: HomeAssistant,
    laundrify_config_entry,
    mock_device: LaundrifyDevice,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update is performed successfully."""
    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coord_entity = get_coord_entity(hass, mock_device)
    assert coord_entity.state != STATE_UNAVAILABLE


async def test_coordinator_update_unauthorized(
    hass: HomeAssistant,
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

    coord_entity = get_coord_entity(hass, mock_device)
    assert coord_entity.state == STATE_UNAVAILABLE


async def test_coordinator_update_connection_failed(
    hass: HomeAssistant,
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

    coord_entity = get_coord_entity(hass, mock_device)
    assert coord_entity.state == STATE_UNAVAILABLE
