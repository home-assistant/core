"""Tests for the Genius Hub component."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.geniushub import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_MAC, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_geniushub_cloud: AsyncMock,
    mock_cloud_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_cloud_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_cloud_config_entry.entry_id)}
    )
    assert device_entry is not None
    assert device_entry == snapshot
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_cloud_config_entry.entry_id}_30")}
    )
    assert device_entry is not None
    assert device_entry == snapshot


async def test_cloud_unique_id_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_geniushub_cloud: AsyncMock,
) -> None:
    """Test that the cloud unique ID is migrated to the entry_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Genius hub",
        data={
            CONF_TOKEN: "abcdef",
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
        },
        entry_id="1234",
    )
    entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN, DOMAIN, "aa:bb:cc:dd:ee:ff_device_78", config_entry=entry
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.geniushub_aa_bb_cc_dd_ee_ff_device_78")
    entity_entry = entity_registry.async_get(
        "sensor.geniushub_aa_bb_cc_dd_ee_ff_device_78"
    )
    assert entity_entry.unique_id == "1234_device_78"
