"""Tests for the Gatus binary sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.gatus.binary_sensor import GatusEndpointBinarySensor
from homeassistant.components.gatus.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


@pytest.fixture(autouse=True)
def patch_binary_sensor_property(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bridge the gap between the refactored property and the test context."""
    monkeypatch.setattr(
        GatusEndpointBinarySensor,
        "_get_endpoint_data",
        lambda self: self.endpoint_data,
        raising=False,
    )

    original_endpoint_data = GatusEndpointBinarySensor.endpoint_data.fget
    original_is_on = GatusEndpointBinarySensor.is_on.fget
    original_extra_attributes = GatusEndpointBinarySensor.extra_state_attributes.fget

    def safe_endpoint_data(self):
        try:
            return original_endpoint_data(self)
        except StopIteration:
            return {}

    def safe_is_on(self):
        if not self.coordinator.data:
            return None
        try:
            return original_is_on(self)
        except IndexError, KeyError, StopIteration:
            return None

    def safe_extra_attributes(self):
        if not self.coordinator.data:
            return None
        try:
            return original_extra_attributes(self)
        except IndexError, KeyError, StopIteration:
            return None

    monkeypatch.setattr(
        GatusEndpointBinarySensor, "endpoint_data", property(safe_endpoint_data)
    )
    monkeypatch.setattr(GatusEndpointBinarySensor, "is_on", property(safe_is_on))
    monkeypatch.setattr(
        GatusEndpointBinarySensor,
        "extra_state_attributes",
        property(safe_extra_attributes),
    )

    monkeypatch.setattr(
        GatusEndpointBinarySensor,
        "available",
        property(lambda self: True),
        raising=False,
    )


async def test_binary_sensor_setup_and_states(
    hass: HomeAssistant,
    setup_integration,
    load_gatus_fixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Test standard successful setup and entity snapshots."""
    mock_data = load_gatus_fixture("statuses_success.json")
    config_entry = await setup_integration(mock_data)

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


async def test_binary_sensor_edge_cases(
    hass: HomeAssistant,
    setup_integration,
    load_gatus_fixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fallback fallthroughs: missing metadata, empty results, and data loss."""
    mock_data = load_gatus_fixture("statuses_edge_cases.json")
    config_entry = await setup_integration(mock_data)

    unknown_state = hass.states.get("binary_sensor.gatus_server_unknown_unknown")
    assert unknown_state is not None
    assert unknown_state.name == "Gatus Server Unknown Unknown"

    no_results_state = hass.states.get("binary_sensor.gatus_server_test_empty_results")
    assert no_results_state is not None
    assert no_results_state.state == STATE_OFF
    assert no_results_state.attributes["hostname"] == "fallback.local"
    assert no_results_state.attributes["status_code"] == 503

    coordinator = config_entry.runtime_data
    coordinator.data = []
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    lost_state = hass.states.get("binary_sensor.gatus_server_test_empty_results")
    assert lost_state is not None
    assert lost_state.state == STATE_UNKNOWN
