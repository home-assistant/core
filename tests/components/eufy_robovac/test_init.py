"""Integration tests for Eufy RoboVac setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.eufy_robovac.const import (
    CONF_LOCAL_KEY,
    CONF_PROTOCOL_VERSION,
    DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN, VacuumActivity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry

ENTRY_DATA = {
    CONF_NAME: "Hall Vacuum",
    CONF_MODEL: "T2253",
    CONF_HOST: "192.168.1.50",
    CONF_ID: "abc123",
    CONF_LOCAL_KEY: "abcdefghijklmnop",
    CONF_PROTOCOL_VERSION: "3.3",
}


async def _async_setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an Eufy RoboVac config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ENTRY_DATA[CONF_ID],
        data=ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


async def test_setup_entry_creates_vacuum_and_polls_dps(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Config entry setup should create a vacuum entity and allow polling."""
    mock_get_dps = AsyncMock(
        return_value={
            "15": "standby",
            "102": "Max",
            "104": "72",
            "106": "0",
        }
    )

    with patch(
        "homeassistant.components.eufy_robovac.local_api.EufyRoboVacLocalApi.async_get_dps",
        mock_get_dps,
    ):
        config_entry = await _async_setup_entry(hass)

        entity_id = entity_registry.async_get_entity_id(
            VACUUM_DOMAIN, DOMAIN, config_entry.data[CONF_ID]
        )
        assert entity_id is not None

        battery_entity_id = entity_registry.async_get_entity_id(
            SENSOR_DOMAIN,
            DOMAIN,
            f"{config_entry.data[CONF_ID]}_battery",
        )
        assert battery_entity_id is not None

        calls_before_update = mock_get_dps.await_count
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == VacuumActivity.IDLE
        assert state.attributes["fan_speed"] == "max"
        assert state.attributes["status_raw"] == "standby"
        assert state.attributes["model_name"] == "G30 Hybrid"
        assert mock_get_dps.await_count == calls_before_update + 1

        battery_state = hass.states.get(battery_entity_id)
        assert battery_state is not None
        assert battery_state.state == "72"
        assert battery_state.attributes["device_class"] == "battery"


async def test_unload_entry_removes_vacuum_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Unloading config entry should unload integration runtime data."""
    with patch(
        "homeassistant.components.eufy_robovac.local_api.EufyRoboVacLocalApi.async_get_dps",
        AsyncMock(return_value={"15": "standby"}),
    ):
        config_entry = await _async_setup_entry(hass)

    entity_id = entity_registry.async_get_entity_id(
        VACUUM_DOMAIN, DOMAIN, config_entry.data[CONF_ID]
    )
    assert entity_id is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(entity_id) is not None
