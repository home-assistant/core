"""Tests for the Aprilaire integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyaprilaire.const import Attribute
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aprilaire.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

DEVICE_IDENTIFIER = (DOMAIN, "12:34:56:78:90:ab")


async def _async_setup_integration(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, AsyncMock]:
    """Set up the integration with a mocked client."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12:34:56:78:90:ab",
        data={CONF_HOST: "localhost", CONF_PORT: 7000},
    )
    config_entry.add_to_hass(hass)

    client = AsyncMock()
    client.stop_listen = MagicMock()
    client.data = {
        Attribute.MAC_ADDRESS: "1234567890ab",
        Attribute.NAME: "Aprilaire",
        Attribute.MODEL_NUMBER: 0,
        Attribute.HARDWARE_REVISION: ord("B"),
        Attribute.FIRMWARE_MAJOR_REVISION: 1,
        Attribute.FIRMWARE_MINOR_REVISION: 5,
        Attribute.THERMOSTAT_MODES: 0,
        Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS: 0,
        Attribute.CONNECTED: True,
    }

    with patch(
        "homeassistant.components.aprilaire.coordinator.pyaprilaire.client.AprilaireClient",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry, client


async def test_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the network MAC connection."""
    config_entry, _ = await _async_setup_integration(hass)

    device_entry = device_registry.async_get_device_by_identifier(
        DEVICE_IDENTIFIER, config_entry.entry_id
    )
    assert device_entry == snapshot


async def test_device_registry_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device registry entry follows a change of the device info."""
    config_entry, client = await _async_setup_integration(hass)

    config_entry.runtime_data.async_set_updated_data(
        client.data
        | {
            Attribute.MODEL_NUMBER: 1,
            Attribute.FIRMWARE_MAJOR_REVISION: 2,
            Attribute.FIRMWARE_MINOR_REVISION: 7,
        }
    )
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        DEVICE_IDENTIFIER, config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.model == "8810"
    assert device_entry.sw_version == "2.07"
