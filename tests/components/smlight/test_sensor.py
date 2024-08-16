"""Tests for the SMLIGHT sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = [
    pytest.mark.usefixtures(
        "setup_platform",
        "mock_smlight_client",
    )
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.slzb_06_core_chip_temp",
        "sensor.slzb_06_zigbee_chip_temp",
        "sensor.slzb_06_ram_usage",
        "sensor.slzb_06_filesystem_usage",
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the SMLIGHT sensors."""

    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot

    assert entry.device_id
    assert (device_entry := device_registry.async_get(entry.device_id))
    assert device_entry == snapshot


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.slzb_06_ram_usage",
        "sensor.slzb_06_filesystem_usage",
    ],
)
async def test_disabled_by_default_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test the disabled by default SMLIGHT sensors."""
    assert not hass.states.get(entity_id)

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
