"""Tests for Homevolt diagnostics."""

from __future__ import annotations

from syrupy.assertion import SnapshotAssertion  # noqa: F401

from homeassistant.core import HomeAssistant

from .conftest import DEVICE_IDENTIFIER

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test config entry diagnostics."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    assert isinstance(diagnostics, dict)

    assert "config" in diagnostics
    assert isinstance(diagnostics["config"], dict)

    assert "coordinator" in diagnostics
    assert "device" in diagnostics
    assert "sensors" in diagnostics
    assert "device_metadata" in diagnostics
    assert "ems" in diagnostics

    coordinator = diagnostics["coordinator"]
    assert coordinator["last_update_success"] is True
    assert coordinator["last_exception"] is None

    device = diagnostics["device"]
    assert device["unique_id"] == "40580137858664"
    assert device["base_url"] == "http://127.0.0.1"

    sensors = diagnostics["sensors"]
    assert isinstance(sensors, dict)
    assert sensors

    device_metadata = diagnostics["device_metadata"]
    assert isinstance(device_metadata, dict)
    assert device_metadata

    ems = diagnostics["ems"]
    assert isinstance(ems, dict)
    assert DEVICE_IDENTIFIER in ems

    ems_device = ems[DEVICE_IDENTIFIER]
    assert "name" in ems_device
    assert "model" in ems_device
    assert "sensors" in ems_device
    assert isinstance(ems_device["sensors"], dict)
    assert ems_device["sensors"]
