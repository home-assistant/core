"""Tests for Hypontech sensors."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hypontech.const import CONF_OEM, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    mock_hyponcloud: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Hypontech sensors."""
    with patch("homeassistant.components.hypontech._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_device_manufacturer_uses_oem(
    hass: HomeAssistant,
    mock_hyponcloud: AsyncMock,
) -> None:
    """Test device manufacturer uses the selected OEM."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test-password",
            CONF_OEM: 4,
        },
        unique_id="4:2123456789123456789",
    )

    with patch("homeassistant.components.hypontech._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    device_registry = dr.async_get(hass)
    overview_device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert overview_device
    assert overview_device.manufacturer == "Nexen"

    plant = mock_hyponcloud.get_list.return_value[0]
    plant_device = device_registry.async_get_device(
        identifiers={(DOMAIN, plant.plant_id)}
    )
    assert plant_device
    assert plant_device.manufacturer == "Nexen"
