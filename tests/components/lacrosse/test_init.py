"""Tests for the LaCrosse integration setup."""

from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest
from serial import SerialException

from homeassistant.components.lacrosse import async_remove_config_entry_device
from homeassistant.components.lacrosse.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USER,
    ConfigEntryState,
    ConfigSubentry,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceRegistry

from tests.common import MockConfigEntry

ENTRY_DATA = {
    "device": "/dev/ttyUSB0",
    "baud": 57600,
    "datarate": 57600,
    "frequency": 868300,
    "led": True,
    "toggle_interval": 5,
    "toggle_mask": 255,
}


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a receiver with a configured sensor subentry."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    sensors = {
        "outdoor_temperature": {
            "id": 1,
            "type": "temperature",
            "expire_after": 300,
            "friendly_name": "Outdoor",
            "unique_id": "outdoor_temperature_unique",
        }
    }
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType({"sensors": sensors}),
            subentry_type="sensor",
            title="LaCrosse sensor 1",
            unique_id="1",
        ),
    )
    return entry


async def test_setup_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting up and unloading a config entry."""
    entry = config_entry
    receiver = MagicMock()

    with patch(
        "homeassistant.components.lacrosse.pylacrosse.LaCrosse",
        return_value=receiver,
    ) as mock_lacrosse:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        mock_lacrosse.assert_called_once_with("/dev/ttyUSB0", 57600)
        receiver.open.assert_called_once()
        receiver.led_mode_state.assert_called_once_with(True)
        receiver.set_frequency.assert_called_once_with(868300)
        assert type(receiver.set_frequency.call_args.args[0]) is int
        receiver.set_datarate.assert_called_once_with(57600)
        receiver.set_toggle_interval.assert_called_once_with(5)
        receiver.set_toggle_mask.assert_called_once_with(255)
        receiver.start_scan.assert_called_once()
        receiver.register_callback.assert_called_once()

        entity_entry = entity_registry.async_get("sensor.outdoor_temperature")
        assert entity_entry is not None
        assert entity_entry.unique_id == "outdoor_temperature_unique"

        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, "/dev/ttyUSB0_1"), entry.entry_id
        )
        assert device is not None
        assert entity_entry.device_id == device.id
        assert device.config_subentry_id == entity_entry.config_subentry_id
        assert device.config_subentry_id in entry.subentries

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert receiver.close.call_count == 1


async def test_yaml_import_keeps_legacy_entity_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test YAML import keeps the legacy entity ID based on its sensor key."""
    with (
        patch(
            "homeassistant.components.lacrosse.config_flow.usb.get_serial_by_id",
            return_value="/dev/ttyUSB0",
        ),
        patch("homeassistant.components.lacrosse.pylacrosse.LaCrosse"),
    ):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                **ENTRY_DATA,
                "sensors": {"livingroom": {"id": 1, "type": "temperature"}},
            },
        )
        await hass.async_block_till_done()

    assert entity_registry.async_get("sensor.livingroom") is not None


async def test_remove_sensor_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test deleting a running device removes its configuration permanently."""
    entry = config_entry
    with patch("homeassistant.components.lacrosse.pylacrosse.LaCrosse"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, "/dev/ttyUSB0_1"), entry.entry_id
        )
        assert device is not None
        assert await async_remove_config_entry_device(hass, entry, device)
        await hass.async_block_till_done()
        assert not entry.subentries
        assert device_registry.async_get(device.id) is None
        assert entity_registry.async_get("sensor.outdoor_temperature") is None
        assert hass.states.get("sensor.outdoor_temperature") is None
        assert entry.state is ConfigEntryState.LOADED
        assert await hass.config_entries.async_reload(entry.entry_id)
        assert device_registry.async_get(device.id) is None


async def test_remove_device_without_sensor_subentry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test devices without a sensor subentry cannot be removed by the integration."""
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "/dev/ttyUSB0_orphan")},
    )

    assert not await async_remove_config_entry_device(hass, config_entry, device)
    assert config_entry.subentries


async def test_add_sensor_to_running_hub(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test adding a sensor reloads a running hub and creates its device."""
    entry = config_entry
    with patch("homeassistant.components.lacrosse.pylacrosse.LaCrosse"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "sensor"), context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"id": 2, "temperature": True, "humidity": True, "battery": True},
        )
        await hass.async_block_till_done()
        subentry = next(
            subentry
            for subentry in entry.subentries.values()
            if subentry.unique_id == "2"
        )
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, "/dev/ttyUSB0_2"), entry.entry_id
        )
        assert device is not None
        assert device.config_subentry_id == subentry.subentry_id
        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        assert len(entities) == 4
        assert {
            entity.config_subentry_id
            for entity in entities
            if entity.device_id == device.id
        } == {subentry.subentry_id}
        assert hass.states.get("sensor.outdoor_temperature") is not None
        assert entry.state is ConfigEntryState.LOADED


async def test_close_receiver_on_home_assistant_stop(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the receiver closes when Home Assistant stops."""
    entry = config_entry
    receiver = MagicMock()

    with patch(
        "homeassistant.components.lacrosse.pylacrosse.LaCrosse",
        return_value=receiver,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    receiver.close.assert_called_once()


async def test_setup_serial_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that an unavailable receiver retries setup."""
    entry = config_entry

    with patch(
        "homeassistant.components.lacrosse.pylacrosse.LaCrosse"
    ) as mock_lacrosse:
        mock_lacrosse.side_effect = SerialException("unavailable")
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_serial_error_during_scan(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the receiver closes when starting the scan fails."""
    entry = config_entry
    receiver = MagicMock()
    receiver.start_scan.side_effect = SerialException("unavailable")

    with patch(
        "homeassistant.components.lacrosse.pylacrosse.LaCrosse",
        return_value=receiver,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    receiver.close.assert_called_once()
