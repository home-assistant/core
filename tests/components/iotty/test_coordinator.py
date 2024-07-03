"""Test the IottyDataUpdateCoordinator component."""

from aiohttp import ClientSession
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.iotty.const import DOMAIN
from homeassistant.components.iotty.coordinator import (
    UPDATE_INTERVAL,
    IottyDataUpdateCoordinator,
)
from homeassistant.components.iotty.switch import IottyLightSwitch, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .conftest import test_ls

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_async_update_data_twodevices_withstatus(
    mock_config_entry: MockConfigEntry,
    hass: HomeAssistant,
    local_oauth_impl: ClientSession,
    mock_get_status_filled,
    mock_schedule_update_ha_state,
    mock_get_devices_twolightswitches,
    # To avoid first call to update_data
    mock_async_first_refresh,
    mock_update_status,
    mock_config_entries_async_forward_entry_setup,
    # mock_handle_coordinator_update
    mock_async_write_ha_state,
) -> None:
    """Get status and store it."""

    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )
    await hass.async_block_till_done()

    sut_coordinator = IottyDataUpdateCoordinator(
        hass, mock_config_entry, local_oauth_impl
    )
    assert sut_coordinator is not None

    await sut_coordinator.async_config_entry_first_refresh()
    await hass.async_block_till_done()

    test_device_1 = IottyLightSwitch(sut_coordinator, sut_coordinator.iotty, test_ls[0])

    test_device_2 = IottyLightSwitch(sut_coordinator, sut_coordinator.iotty, test_ls[1])

    await sut_coordinator._async_update_data()
    await sut_coordinator._async_refresh()
    await hass.async_block_till_done()
    test_device_1._handle_coordinator_update()
    test_device_2._handle_coordinator_update()

    assert len(mock_async_write_ha_state.mock_calls) == 2


async def test_async_update_data_trigger_listeners(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twodevices,
    mock_get_status_filled,
    mock_async_add_entities: AddEntitiesCallback,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Update time by update interval and see if listeners are triggered."""

    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )
    await hass.async_block_till_done()

    sut_coordinator = IottyDataUpdateCoordinator(
        hass, mock_config_entry, local_oauth_impl
    )
    assert sut_coordinator is not None

    await sut_coordinator.async_config_entry_first_refresh()
    await hass.async_block_till_done()

    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = sut_coordinator
    await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(mock_async_add_entities.mock_calls) == 2
