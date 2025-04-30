"""Test Fing Agent device tracker entity."""

from datetime import timedelta

from fing_agent_api.models import DeviceResponse
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.fing.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import async_fire_time_changed, load_json_object_fixture


async def test_device_tracker_init(
    hass: HomeAssistant,
    mocked_entry,
    mocked_fing_agent,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Fing device tracker setup."""
    entry = await init_integration(hass, mocked_entry, mocked_fing_agent)
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 3


async def test_new_device_found(
    hass: HomeAssistant,
    mocked_entry,
    mocked_fing_agent,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Fing device tracker setup."""

    delta_time = timedelta(seconds=35)  # 30 seconds + 5 delta seconds

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    entry = await init_integration(hass, mocked_entry, mocked_fing_agent)

    # First check -> there are 3 devices in total
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 3

    mocked_fing_agent.get_devices.return_value = DeviceResponse(
        load_json_object_fixture("device_resp_device_added.json", DOMAIN)
    )

    freezer.tick(delta_time)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Second check -> added one device
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 4

    mocked_fing_agent.get_devices.return_value = DeviceResponse(
        load_json_object_fixture("device_resp_device_deleted.json", DOMAIN)
    )

    freezer.tick(delta_time)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Third check -> removed two devices (old devices)
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 2
