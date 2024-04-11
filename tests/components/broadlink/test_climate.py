"""Tests for Broadlink sensors."""

from homeassistant.components.broadlink.climate import SERVICE_SYNC_TIME
from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import get_device


async def test_sync_time_service(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sync time for a thermostat."""
    device = get_device("Guest room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    thermostats = [entry for entry in entries if entry.domain == Platform.CLIMATE]
    assert len(thermostats) == 1

    thermostat = thermostats[0]
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SYNC_TIME,
        target={"entity_id": thermostat.entity_id},
        blocking=True,
    )

    assert mock_setup.api.set_time.call_count == 1
