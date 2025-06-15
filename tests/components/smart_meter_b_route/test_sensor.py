"""Tests for the Smart Meter B-Route sensor."""

from freezegun.api import FrozenDateTimeFactory
from momonga import MomongaError
import pytest

from homeassistant.components.smart_meter_b_route.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import CONF_ID, configure_integration, user_input

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_async_setup_entry_with_non_existing_bid(
    hass: HomeAssistant, mock_momonga
) -> None:
    """Test async_setup_entry function."""
    config_entry = configure_integration(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.config_entries.async_get_entry(config_entry.entry_id).state
        == ConfigEntryState.LOADED
    )


async def test_async_setup_entry_with_existing_bid(
    hass: HomeAssistant, mock_momonga
) -> None:
    """Test async_setup_entry function."""
    config_entry = configure_integration(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        hass.config_entries.async_get_entry(config_entry.entry_id).state
        == ConfigEntryState.LOADED
    )

    same_bid_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**user_input, CONF_DEVICE: "/dev/ttyUSB43"},
        entry_id="987654",
        unique_id="987654",
    )
    same_bid_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(same_bid_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        hass.config_entries.async_get_entry(config_entry.entry_id).data[CONF_ID]
        == hass.config_entries.async_get_entry(same_bid_config_entry.entry_id).data[
            CONF_ID
        ]
    )
    assert (
        hass.config_entries.async_get_entry(config_entry.entry_id).unique_id
        != hass.config_entries.async_get_entry(same_bid_config_entry.entry_id).unique_id
    )
    assert (
        hass.config_entries.async_get_entry(same_bid_config_entry.entry_id).state
        == ConfigEntryState.SETUP_ERROR
    )


@pytest.mark.parametrize(
    ("index", "entity_id"),
    [
        (0, "sensor.smart_meter_b_route_b_route_id_instantaneous_current_r_phase"),
        (1, "sensor.smart_meter_b_route_b_route_id_instantaneous_current_t_phase"),
        (2, "sensor.smart_meter_b_route_b_route_id_instantaneous_power"),
        (3, "sensor.smart_meter_b_route_b_route_id_total_consumption"),
    ],
)
async def test_smart_meter_b_route_sensor_update(
    hass: HomeAssistant,
    index: int,
    entity_id: str,
    mock_momonga,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test SmartMeterBRouteSensor update."""
    config_entry = configure_integration(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(entity_id)
    assert entity.state == str(index + 1)


async def test_smart_meter_b_route_sensor_no_update(
    hass: HomeAssistant,
    mock_momonga,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test SmartMeterBRouteSensor with no update."""

    entity_id = "sensor.smart_meter_b_route_b_route_id_instantaneous_current_r_phase"
    config_entry = configure_integration(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_momonga.return_value.get_instantaneous_current.side_effect = MomongaError
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(entity_id)
    assert entity.state is STATE_UNAVAILABLE
