"""Tests for Wibeee sensors."""

from unittest.mock import MagicMock

from homeassistant.components.wibeee.const import (
    CONF_MAC_ADDRESS,
    CONF_WIBEEE_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_HOST, MOCK_MAC, MOCK_WIBEEE_ID

from tests.common import MockConfigEntry


async def test_sensors_created(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test that sensor entities are created."""
    entity_ids = {state.entity_id for state in hass.states.async_all("sensor")}
    assert "sensor.wibeee_112233_total_active_power" in entity_ids
    assert "sensor.wibeee_112233_l1_active_power" in entity_ids


async def test_sensor_state_class(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test sensor has correct state class."""
    state = hass.states.get("sensor.wibeee_112233_total_active_power")
    assert state.attributes.get("state_class") == "measurement"


async def test_sensors_consumed_produced_energy(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Newer firmware reports energy in separate consumed/produced counters."""
    mock_wibeee_api.async_fetch_sensors_data.return_value = {
        "fase4": {
            "energia_activa": "0",
            "energia_activa_cons": "1587",
            "energia_activa_prod": "2149",
        },
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_MAC,
        title="Wibeee 112233",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_MAC_ADDRESS: MOCK_MAC,
            CONF_WIBEEE_ID: MOCK_WIBEEE_ID,
        },
        options={},
        version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    consumed = hass.states.get("sensor.wibeee_112233_total_consumed_active_energy")
    assert consumed is not None
    assert consumed.state == "1587.0"
    assert consumed.attributes.get("state_class") == "total_increasing"

    produced = hass.states.get("sensor.wibeee_112233_total_produced_active_energy")
    assert produced is not None
    assert produced.state == "2149.0"

    # The legacy aggregate stays at 0 on this firmware; it must not be created.
    assert hass.states.get("sensor.wibeee_112233_total_active_energy") is None


async def test_sensor_unavailable_on_coordinator_failure(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, mock_wibeee_api: MagicMock
) -> None:
    """Sensors go unavailable when a coordinator refresh fails."""
    mock_wibeee_api.async_fetch_sensors_data.side_effect = TimeoutError

    coordinator = loaded_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wibeee_112233_total_active_power")
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_invalid_value(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test a sensor becomes unknown when its value is not numeric."""
    coordinator = loaded_entry.runtime_data
    coordinator.async_set_updated_data(
        {
            "fase1": {"vrms": "230.5", "p_activa": "277"},
            "fase4": {"vrms": "230.5", "p_activa": "not_a_number"},
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wibeee_112233_total_active_power")
    assert state.state == STATE_UNKNOWN


async def test_sensor_unavailable_on_missing_key(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test a sensor goes unavailable when a later payload omits its key."""
    coordinator = loaded_entry.runtime_data
    coordinator.async_set_updated_data(
        {
            "fase1": {"vrms": "230.5", "p_activa": "277"},
            "fase4": {"vrms": "230.5"},
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wibeee_112233_total_active_power")
    assert state.state == STATE_UNAVAILABLE


async def test_sensors_polling_mode_keeps_all_keys(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_wibeee_api: MagicMock,
) -> None:
    """Polling mode keeps all sensors, including disabled-by-default metrics."""
    mock_wibeee_api.async_fetch_sensors_data.return_value = {
        "fase4": {"p_activa": "120", "angle": "33"},
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_MAC,
        title="Wibeee 112233",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_MAC_ADDRESS: MOCK_MAC,
            CONF_WIBEEE_ID: MOCK_WIBEEE_ID,
        },
        options={},
        version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # angle is disabled-by-default, so check the entity registry
    assert (
        entity_registry.async_get(f"sensor.wibeee_{MOCK_MAC[-6:]}_total_active_power")
        is not None
    )
    assert (
        entity_registry.async_get(f"sensor.wibeee_{MOCK_MAC[-6:]}_total_phase_angle")
        is not None
    )


async def test_sensor_setup_no_known_phases(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Setup fails and retries when the device returns no known phases."""
    mock_wibeee_api.async_fetch_sensors_data.return_value = {
        "unknown_phase": {"vrms": "230"},
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_MAC,
        title="Wibeee 112233",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_MAC_ADDRESS: MOCK_MAC,
            CONF_WIBEEE_ID: MOCK_WIBEEE_ID,
        },
        options={},
        version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.async_all("sensor") == []
