"""Tests for the Vivotek camera integration."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vivotek.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_camera_device_info(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the camera is linked to a device with expected metadata."""
    mock_vivotek_camera.get_serial.return_value = "ABCD1234"
    mock_vivotek_camera.get_param.side_effect = lambda key: {
        "system_info_firmwareversion": "1.2.3",
        "system_info_modelname": "FD9165-HT",
    }[key]

    await setup_integration(hass, mock_config_entry)

    entity_entry = entity_registry.async_get("camera.vivotek_camera")
    assert entity_entry is not None
    assert entity_entry.device_id is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert (DOMAIN, "11:22:33:44:55:66") in device.identifiers
    assert (dr.CONNECTION_NETWORK_MAC, "11:22:33:44:55:66") in device.connections
    assert device.manufacturer == "VIVOTEK"
    assert device.model == "FD9165-HT"
    assert device.serial_number == "ABCD1234"
    assert device.sw_version == "1.2.3"
