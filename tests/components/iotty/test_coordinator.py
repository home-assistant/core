"""Test the IottyDataUpdateCoordinator component."""


from aiohttp import ClientSession

from homeassistant.components.iotty.api import IottyProxy
from homeassistant.components.iotty.const import DOMAIN
from homeassistant.components.iotty.coordinator import IottyDataUpdateCoordinator
from homeassistant.components.iotty.switch import IottyLightSwitch
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import test_ls

from tests.common import MockConfigEntry


async def test_store_entity_double_id_only_one(
    mock_config_entry: MockConfigEntry,
    hass: HomeAssistant,
    local_oauth_impl,
    aiohttp_client_session,
    mock_iotty: IottyProxy,
) -> None:
    """Store an entity twice."""

    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )
    await hass.async_block_till_done()

    sut_coordinator = IottyDataUpdateCoordinator(
        hass, mock_config_entry, aiohttp_client_session
    )
    assert sut_coordinator is not None

    sut_coordinator.store_entity(
        test_ls[0].device_id, IottyLightSwitch(sut_coordinator, mock_iotty, test_ls[0])
    )

    assert len(sut_coordinator._entities) == 1

    # Other device, same ID
    sut_coordinator.store_entity(
        test_ls[0].device_id, IottyLightSwitch(sut_coordinator, mock_iotty, test_ls[1])
    )

    assert len(sut_coordinator._entities) == 1


async def test_store_entity_two_devices_ok(
    mock_config_entry: MockConfigEntry,
    hass: HomeAssistant,
    local_oauth_impl,
    aiohttp_client_session,
    mock_iotty: IottyProxy,
) -> None:
    """Store an entity twice."""

    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )
    await hass.async_block_till_done()

    sut_coordinator = IottyDataUpdateCoordinator(
        hass, mock_config_entry, aiohttp_client_session
    )
    assert sut_coordinator is not None

    sut_coordinator.store_entity(
        test_ls[0].device_id, IottyLightSwitch(sut_coordinator, mock_iotty, test_ls[0])
    )

    # Other device
    sut_coordinator.store_entity(
        test_ls[1].device_id, IottyLightSwitch(sut_coordinator, mock_iotty, test_ls[1])
    )

    assert len(sut_coordinator._entities) == 2


async def test_first_refresh_call_ok(
    mock_config_entry: MockConfigEntry,
    hass: HomeAssistant,
    local_oauth_impl: ClientSession,
    mock_get_devices_twodevices,
    mock_async_first_refresh,
    mock_config_entries_async_forward_entry_setup,
) -> None:
    """Store an entity twice."""

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

    assert len(mock_get_devices_twodevices.mock_calls) == 1

    assert len(sut_coordinator._devices) == 2

    assert len(mock_async_first_refresh.mock_calls) == 1

    assert len(mock_config_entries_async_forward_entry_setup.mock_calls) == 1


async def test_first_refresh_twodevices_ok(
    mock_config_entry: MockConfigEntry,
    hass: HomeAssistant,
    local_oauth_impl: ClientSession,
    mock_get_devices_twodevices,
    mock_get_status_filled,
    mock_config_entries_async_forward_entry_setup,
) -> None:
    """Store an entity twice."""

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

    assert len(mock_get_devices_twodevices.mock_calls) == 1

    assert len(sut_coordinator._devices) == 2

    assert len(mock_get_status_filled.mock_calls) == 2


async def test_async_update_data_twodevices_nostatus(
    mock_config_entry: MockConfigEntry,
    hass: HomeAssistant,
    local_oauth_impl: ClientSession,
    mock_get_status_empty,
    mock_schedule_update_ha_state,
    mock_get_devices_twodevices,
    # To avoid first call to update_data
    mock_async_first_refresh,
    mock_update_status,
    mock_config_entries_async_forward_entry_setup,
) -> None:
    """Get status and don't store anything, because get_status returns a wrong object."""

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

    assert len(mock_get_devices_twodevices.mock_calls) == 1

    assert len(sut_coordinator._devices) == 2

    await sut_coordinator._async_update_data()

    # Because get_status failed
    assert len(mock_update_status.mock_calls) == 0


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
    sut_coordinator.store_entity(test_ls[0].device_id, test_device_1)

    test_device_2 = IottyLightSwitch(sut_coordinator, sut_coordinator.iotty, test_ls[1])
    sut_coordinator.store_entity(
        test_ls[1].device_id,
        test_device_2,
    )

    await sut_coordinator._async_update_data()
    await sut_coordinator._async_refresh()
    await hass.async_block_till_done()
    test_device_1._handle_coordinator_update()
    test_device_2._handle_coordinator_update()

    assert len(mock_async_write_ha_state.mock_calls) == 2
