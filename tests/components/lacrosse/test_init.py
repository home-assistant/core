"""Tests for the LaCrosse integration setup."""

from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from serial import SerialException

from homeassistant.components.lacrosse import async_remove_config_entry_device
from homeassistant.components.lacrosse.const import (
    CONF_YAML_IMPORTED,
    DOMAIN,
    sensor_entity_key,
)
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


async def test_receivers_with_same_sensor_key(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test identical sensor keys on different receivers remain independent."""
    second_entry = MockConfigEntry(
        domain=DOMAIN, data={**ENTRY_DATA, "device": "/dev/ttyUSB1"}
    )

    with patch("homeassistant.components.lacrosse.pylacrosse.LaCrosse"):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        second_entry.add_to_hass(hass)
        hass.config_entries.async_add_subentry(
            second_entry,
            ConfigSubentry(
                data=next(iter(config_entry.subentries.values())).data,
                subentry_type="sensor",
                title="LaCrosse sensor 1",
                unique_id="1",
            ),
        )
        assert await hass.config_entries.async_setup(second_entry.entry_id)
        await hass.async_block_till_done()

        for entry in (config_entry, second_entry):
            entity_id = entity_registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_outdoor_temperature"
            )
            assert entity_id is not None
            entity = entity_registry.async_get(entity_id)
            assert entity.config_entry_id == entry.entry_id
            assert entity.config_subentry_id in entry.subentries
            assert hass.states.get(entity_id) is not None

        assert await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == 2


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
        assert entity_entry.unique_id == f"{entry.entry_id}_outdoor_temperature"

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


async def test_sensor_entity_id_survives_sensor_id_change_and_reload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test subentry-based entity IDs survive a sensor ID change and reload."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "sensors": {
                    "temperature": {
                        "id": 1,
                        "type": "temperature",
                        "friendly_name": "Outdoor",
                    }
                }
            }
        ),
        subentry_type="sensor",
        title="Outdoor",
        unique_id="1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    unique_id = (
        f"{entry.entry_id}_{sensor_entity_key(subentry.subentry_id, 'temperature')}"
    )

    with patch("homeassistant.components.lacrosse.pylacrosse.LaCrosse"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None
        assert (
            er.async_get_full_entity_name(hass, entity_registry.async_get(entity_id))
            == "Outdoor Temperature"
        )

        result = await entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"id": 7, "type": "temperature"},
        )
        assert result["reason"] == "reconfigure_successful"
        assert subentry.unique_id == "7"

        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id).unique_id == unique_id


@pytest.mark.parametrize(
    "sensor_type",
    [
        pytest.param("temperature", id="temperature"),
        pytest.param("humidity", id="humidity"),
        pytest.param("battery", id="battery"),
    ],
)
async def test_yaml_import_keeps_legacy_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    sensor_type: str,
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
                "sensors": {sensor_type: {"id": 1, "type": sensor_type}},
            },
        )
        await hass.async_block_till_done()

    assert entity_registry.async_get(f"sensor.{sensor_type}") is not None


async def test_ui_sensors_on_yaml_entry_use_subentry_entity_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test UI-added sensors are namespaced even on a YAML-imported entry."""
    with (
        patch(
            "homeassistant.components.lacrosse.config_flow.usb.get_serial_by_id",
            return_value="/dev/ttyUSB0",
        ),
        patch("homeassistant.components.lacrosse.pylacrosse.LaCrosse"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                **ENTRY_DATA,
                "sensors": {"battery": {"id": 1, "type": "battery"}},
            },
        )
        entry = result["result"]
        for sensor_id in (2, 3):
            result = await hass.config_entries.subentries.async_init(
                (entry.entry_id, "sensor"), context={"source": SOURCE_USER}
            )
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"],
                {
                    "id": sensor_id,
                    "type": "temperature_humidity_battery",
                    "friendly_name": "Outdoor",
                },
            )
            assert result["type"] == "create_entry"
            await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    expected_unique_ids = {f"{entry.entry_id}_battery"}
    for subentry in entry.subentries.values():
        if subentry.data.get(CONF_YAML_IMPORTED):
            continue
        expected_unique_ids.update(
            f"{entry.entry_id}_{sensor_entity_key(subentry.subentry_id, sensor_type)}"
            for sensor_type in ("temperature", "humidity", "battery")
        )

    assert {entity.unique_id for entity in entities} == expected_unique_ids
    assert len(entities) == 7
    assert entity_registry.async_get("sensor.battery") is not None


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
            {"id": 2, "type": "temperature_humidity_battery"},
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
