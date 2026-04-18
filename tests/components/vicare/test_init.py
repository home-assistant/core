"""Test ViCare migration."""

from unittest.mock import patch

from homeassistant.components.vicare.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import ENTRY_CONFIG, MODULE
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry


async def test_migrate_entry_v1_1_to_v1_2(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> None:
    """Test migration of config entry from v1.1 to v1.2 removes heating_type."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={**ENTRY_CONFIG, "heating_type": "auto"},
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 1
    assert config_entry.minor_version == 2
    assert "heating_type" not in config_entry.data


async def test_migrate_entry_v1_1_to_v1_2_no_heating_type(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> None:
    """Test migration of config entry from v1.1 to v1.2 when heating_type is absent."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data=ENTRY_CONFIG,
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 1
    assert config_entry.minor_version == 2
    assert "heating_type" not in config_entry.data


# Device migration test can be removed in 2025.4.0
async def test_device_and_entity_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the device registry is updated correctly."""
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json"),
        Fixture({"type:boiler"}, "vicare/dummy-device-no-serial.json"),
    ]
    with (
        patch(f"{MODULE}.login", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.CLIMATE]),
    ):
        mock_config_entry.add_to_hass(hass)

        # device with serial data point
        device0 = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={
                (DOMAIN, "gateway0"),
            },
            model="model0",
        )
        entry0 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway0-0",
            translation_key="heating",
            device_id=device0.id,
        )
        entry1 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway0_deviceSerialVitodens300W-heating-1",
            translation_key="heating",
            device_id=device0.id,
        )
        # device without serial data point
        device1 = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={
                (DOMAIN, "gateway1"),
            },
            model="model1",
        )
        entry2 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway1-0",
            translation_key="heating",
            device_id=device1.id,
        )
        # device is not provided by api
        device2 = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={
                (DOMAIN, "gateway2"),
            },
            model="model2",
        )
        entry3 = entity_registry.async_get_or_create(
            domain=Platform.CLIMATE,
            platform=DOMAIN,
            config_entry=mock_config_entry,
            unique_id="gateway2-0",
            translation_key="heating",
            device_id=device2.id,
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        await hass.async_block_till_done()

    assert (
        entity_registry.async_get(entry0.entity_id).unique_id
        == "gateway0_deviceSerialVitodens300W-heating-0"
    )
    assert (
        entity_registry.async_get(entry1.entity_id).unique_id
        == "gateway0_deviceSerialVitodens300W-heating-1"
    )
    assert (
        entity_registry.async_get(entry2.entity_id).unique_id
        == "gateway1_deviceId1-heating-0"
    )
    assert entity_registry.async_get(entry3.entity_id).unique_id == "gateway2-0"
