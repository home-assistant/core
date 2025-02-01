"""Unit tests the Hass COVER component."""

from aiohttp import ClientSession
from freezegun.api import FrozenDateTimeFactory
from iottycloud.verbs import (
    OPEN_PERCENTAGE,
    RESULT,
    STATUS,
    STATUS_CLOSING,
    STATUS_OPENING,
    STATUS_STATIONATRY,
)

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    CoverState,
)
from homeassistant.components.iotty.const import DOMAIN
from homeassistant.components.iotty.coordinator import UPDATE_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import test_sh_one_added

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_open_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twoshutters,
    mock_get_status_filled_stationary_0,
    mock_command_fn,
) -> None:
    """Issue an open command."""

    entity_id = "cover.test_shutter_0_test_serial_sh_0"

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.CLOSED

    mock_get_status_filled_stationary_0.return_value = {
        RESULT: {STATUS: STATUS_OPENING, OPEN_PERCENTAGE: 10}
    }

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()
    mock_command_fn.assert_called_once()

    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.OPENING


async def test_close_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twoshutters,
    mock_get_status_filled_stationary_100,
    mock_command_fn,
) -> None:
    """Issue a close command."""

    entity_id = "cover.test_shutter_0_test_serial_sh_0"

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.OPEN

    mock_get_status_filled_stationary_100.return_value = {
        RESULT: {STATUS: STATUS_CLOSING, OPEN_PERCENTAGE: 90}
    }

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()
    mock_command_fn.assert_called_once()

    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.CLOSING


async def test_stop_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twoshutters,
    mock_get_status_filled_opening_50,
    mock_command_fn,
) -> None:
    """Issue a stop command."""

    entity_id = "cover.test_shutter_0_test_serial_sh_0"

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.OPENING

    mock_get_status_filled_opening_50.return_value = {
        RESULT: {STATUS: STATUS_STATIONATRY, OPEN_PERCENTAGE: 60}
    }

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()
    mock_command_fn.assert_called_once()

    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.OPEN


async def test_set_position_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twoshutters,
    mock_get_status_filled_stationary_0,
    mock_command_fn,
) -> None:
    """Issue a set position command."""

    entity_id = "cover.test_shutter_0_test_serial_sh_0"

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.CLOSED

    mock_get_status_filled_stationary_0.return_value = {
        RESULT: {STATUS: STATUS_OPENING, OPEN_PERCENTAGE: 50}
    }

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 10},
        blocking=True,
    )

    await hass.async_block_till_done()
    mock_command_fn.assert_called_once()

    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.OPENING


async def test_devices_insertion_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twoshutters,
    mock_get_status_filled_stationary_0,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test iotty cover insertion."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Should have two devices
    assert hass.states.async_entity_ids_count() == 2
    assert hass.states.async_entity_ids() == [
        "cover.test_shutter_0_test_serial_sh_0",
        "cover.test_shutter_1_test_serial_sh_1",
    ]

    mock_get_devices_twoshutters.return_value = test_sh_one_added

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should have three devices
    assert hass.states.async_entity_ids_count() == 3
    assert hass.states.async_entity_ids() == [
        "cover.test_shutter_0_test_serial_sh_0",
        "cover.test_shutter_1_test_serial_sh_1",
        "cover.test_shutter_2_test_serial_sh_2",
    ]
