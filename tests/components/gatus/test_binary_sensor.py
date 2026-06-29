"""Tests for the Gatus binary sensor platform."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.gatus.const import DOMAIN
from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_binary_sensor_setup_and_states(hass: HomeAssistant) -> None:
    """Test standard successful setup, states, attributes, and device tracking."""
    mock_coordinator_data = [
        {
            "key": "core_frontend",
            "group": "core",
            "name": "frontend",
            "results": [
                {
                    "success": True,
                    "hostname": "frontend.local",
                    "status": 200,
                    "duration": 45000000,
                    "timestamp": "2026-06-29T13:00:00Z",
                }
            ],
        },
        {
            "key": "core_backend",
            "group": "core",
            "name": "backend",
            "results": [
                {
                    "success": False,
                    "hostname": "backend.local",
                    "status": 500,
                    "duration": 95000000,
                    "timestamp": "2026-06-29T13:00:01Z",
                }
            ],
        },
        {
            "group": "ghost",
            "name": "ghost-service",
        },
    ]

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "http://gatus.local"},
        entry_id="gatus_mock_entry_id",
    )
    config_entry.add_to_hass(hass)

    coordinator = GatusDataUpdateCoordinator(hass, config_entry, "http://gatus.local")
    coordinator.data = mock_coordinator_data
    config_entry.runtime_data = coordinator

    config_entry.mock_state(hass, ConfigEntryState.LOADED)

    await hass.config_entries.async_forward_entry_setups(
        config_entry, ["binary_sensor"]
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    frontend_entity_id = "binary_sensor.gatus_server_core_frontend"
    entry = entity_registry.async_get(frontend_entity_id)

    assert entry is not None
    assert entry.unique_id == "gatus_mock_entry_id_core_frontend"
    assert entry.original_name == "Core frontend"

    state = hass.states.get(frontend_entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.CONNECTIVITY

    assert state.attributes.get("hostname") == "frontend.local"
    assert state.attributes.get("status_code") == 200
    assert state.attributes.get("duration_raw") == 45000000
    assert state.attributes.get("timestamp") == "2026-06-29T13:00:00Z"

    backend_state = hass.states.get("binary_sensor.gatus_server_core_backend")
    assert backend_state is not None
    assert backend_state.state == STATE_OFF

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, config_entry.entry_id)}
    )
    assert device_entry is not None
    assert device_entry.name == "Gatus Server"
    assert device_entry.manufacturer == "TwiN"
    assert device_entry.model == "Gatus Monitoring Engine"


async def test_binary_sensor_edge_cases(hass: HomeAssistant) -> None:
    """Test fallback fallthroughs: missing metadata, empty results, and data loss."""
    mock_coordinator_data = [
        {
            "key": "unknown_endpoint",
            "results": [{"success": True, "hostname": "unknown.local"}],
        },
        {
            "key": "no_results_endpoint",
            "group": "test",
            "name": "empty-results",
            "results": [],
        },
    ]

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "http://gatus.local"},
        entry_id="gatus_edge_entry_id",
    )
    config_entry.add_to_hass(hass)

    coordinator = GatusDataUpdateCoordinator(hass, config_entry, "http://gatus.local")
    coordinator.data = mock_coordinator_data
    config_entry.runtime_data = coordinator

    config_entry.mock_state(hass, ConfigEntryState.LOADED)

    await hass.config_entries.async_forward_entry_setups(
        config_entry, ["binary_sensor"]
    )
    await hass.async_block_till_done()

    unknown_state = hass.states.get("binary_sensor.gatus_server_unknown_unknown")
    assert unknown_state is not None
    assert unknown_state.name == "Gatus Server Unknown Unknown"

    no_results_state = hass.states.get("binary_sensor.gatus_server_test_empty_results")
    assert no_results_state is not None
    assert no_results_state.state == STATE_UNKNOWN
    assert "hostname" not in no_results_state.attributes

    coordinator.data = []
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    lost_state = hass.states.get("binary_sensor.gatus_server_test_empty_results")
    assert lost_state is not None
    assert lost_state.state == STATE_UNKNOWN
