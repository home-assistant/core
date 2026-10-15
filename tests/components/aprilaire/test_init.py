"""Tests for the Aprilaire integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyaprilaire.const import Attribute
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aprilaire.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
        minor_version=2,
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


def _mock_client(mac_address: str) -> AsyncMock:
    """Return a mocked client reporting a MAC address."""
    client = AsyncMock()
    client.stop_listen = MagicMock()
    client.data = {
        Attribute.MAC_ADDRESS: mac_address,
        Attribute.THERMOSTAT_MODES: 0,
        Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS: 0,
        Attribute.CONNECTED: True,
    }
    return client


async def _async_setup_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, mac_address: str
) -> None:
    """Set up an entry, which migrates it, with a client reporting a MAC address."""
    with patch(
        "homeassistant.components.aprilaire.coordinator.pyaprilaire.client.AprilaireClient",
        return_value=_mock_client(mac_address),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("old_mac", "new_mac"),
    [
        pytest.param("b4:82:55:0:1a:5", "b4:82:55:00:1a:05", id="unpadded"),
        # format_mac treated the 12 character "0:3:4a:1:2:3" as unseparated
        pytest.param("0::3::4a::1::2::3", "00:03:4a:01:02:03", id="regrouped"),
    ],
)
async def test_migrate_unpadded_mac_address(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    old_mac: str,
    new_mac: str,
) -> None:
    """Test migrating the unpadded MAC address of pyaprilaire < 0.10."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=old_mac,
        data={CONF_HOST: "localhost", CONF_PORT: 7000},
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, old_mac)},
        connections={(dr.CONNECTION_NETWORK_MAC, old_mac)},
    )
    entity_entry = entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        f"{old_mac}_thermostat",
        config_entry=config_entry,
        device_id=device_entry.id,
    )
    other_entity_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "other_unique_id",
        config_entry=config_entry,
    )

    await _async_setup_entry(hass, config_entry, new_mac)

    assert config_entry.minor_version == 2
    assert config_entry.unique_id == new_mac

    entity_entry = entity_registry.async_get(entity_entry.entity_id)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{new_mac}_thermostat"
    assert entity_entry.device_id == device_entry.id

    other_entity_entry = entity_registry.async_get(other_entity_entry.entity_id)
    assert other_entity_entry is not None
    assert other_entity_entry.unique_id == "other_unique_id"

    device_entry = device_registry.async_get(device_entry.id)
    assert device_entry is not None
    assert device_entry.identifiers == {(DOMAIN, new_mac)}
    assert device_entry.connections == {(dr.CONNECTION_NETWORK_MAC, new_mac)}


async def test_migrate_mac_address_unchanged(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrating a unique ID that doesn't need zero-padding."""
    mac_address = "12:34:56:78:90:ab"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mac_address,
        data={CONF_HOST: "localhost", CONF_PORT: 7000},
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    entity_entry = entity_registry.async_get_or_create(
        "climate", DOMAIN, f"{mac_address}_thermostat", config_entry=config_entry
    )

    await _async_setup_entry(hass, config_entry, mac_address)

    assert config_entry.minor_version == 2
    assert config_entry.unique_id == mac_address
    entity_entry = entity_registry.async_get(entity_entry.entity_id)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{mac_address}_thermostat"


async def test_migrate_mac_address_entity_conflict(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrating when a zero-padded entity unique ID is already in use."""
    old_mac = "b4:82:55:0:1a:5"
    new_mac = "b4:82:55:00:1a:05"

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=old_mac,
        data={CONF_HOST: "localhost", CONF_PORT: 7000},
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    old_entity_entry = entity_registry.async_get_or_create(
        "climate", DOMAIN, f"{old_mac}_thermostat", config_entry=config_entry
    )
    new_entity_entry = entity_registry.async_get_or_create(
        "climate", DOMAIN, f"{new_mac}_thermostat", config_entry=config_entry
    )

    await _async_setup_entry(hass, config_entry, new_mac)

    assert config_entry.minor_version == 2
    assert config_entry.unique_id == new_mac

    old_entity_entry = entity_registry.async_get(old_entity_entry.entity_id)
    assert old_entity_entry is not None
    assert old_entity_entry.unique_id == f"{old_mac}_thermostat"
    new_entity_entry = entity_registry.async_get(new_entity_entry.entity_id)
    assert new_entity_entry is not None
    assert new_entity_entry.unique_id == f"{new_mac}_thermostat"
