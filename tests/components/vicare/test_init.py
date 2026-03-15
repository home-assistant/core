"""Test ViCare migration."""

from unittest.mock import patch

from homeassistant.components.vicare.const import CONF_HEATING_TYPE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import MODULE
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry


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
        patch(f"{MODULE}._login", return_value=MockPyViCare(fixtures)),
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


async def test_migration_v1_1_to_v1_2_triggers_reauth(
    hass: HomeAssistant,
) -> None:
    """Test that migrated entry with empty token raises ConfigEntryAuthFailed."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        entry_id="1234",
        version=1,
        minor_version=1,
        data={
            "client_id": "old-client-id",
            "username": "user@example.com",
            "password": "secret",
            CONF_HEATING_TYPE: "gas",
        },
    )
    old_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(old_entry.entry_id)
    await hass.async_block_till_done()

    # Setup should fail with auth error, triggering reauth
    assert old_entry.state is ConfigEntryState.SETUP_ERROR

    # Verify migration happened
    assert old_entry.minor_version == 2
    assert old_entry.data["auth_implementation"] == DOMAIN
    assert old_entry.data["token"] == {}
    assert old_entry.data[CONF_HEATING_TYPE] == "gas"
    # Old credentials should be removed from entry data
    assert "password" not in old_entry.data
    assert "username" not in old_entry.data
