"""Test SenseCAP readings and device lifecycle through LoRaWAN events."""

from dataclasses import replace
from unittest.mock import patch

from lorawan_connection import AddedEvent, DeviceDescriptor, RemovedEvent, UplinkEvent
from lorawan_connection.mock import MockConnection
import pytest
from sensecap_lorawan import S2101, S2102, S2103
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_load_json_object_fixture


@pytest.mark.parametrize("stack", ["chirpstack", "tts"])
@pytest.mark.parametrize(
    ("model", "fixture_name"), [(S2101, "s2101.json"), (S2102, "s2102.json")]
)
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    descriptor: DeviceDescriptor,
    stack: str,
    model: type[S2101 | S2102],
    fixture_name: str,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Replay physical-device payloads through each official catalog identity."""
    descriptor = replace(descriptor, model_id=model.identifiers[stack][1])
    mock_connection.emit(
        AddedEvent(descriptor=descriptor, received_at=dt_util.utcnow())
    )
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    fixture = await async_load_json_object_fixture(hass, fixture_name, "sensecap")
    for key in fixture["expected"]:
        assert hass.states.get(f"sensor.greenhouse_{key}").state == "unknown"
    mock_connection.emit(
        UplinkEvent(
            descriptor=descriptor,
            received_at=dt_util.utcnow(),
            f_port=fixture["f_port"],
            data=bytes.fromhex(fixture["payload"]),
        )
    )
    await hass.async_block_till_done()
    for key, value in fixture["expected"].items():
        entity_id = f"sensor.greenhouse_{key}"
        assert hass.states.get(entity_id).state == str(value)
        assert hass.states.get(entity_id) == snapshot(name=key)
        assert (
            entity_registry.async_get(entity_id).unique_id
            == f"network:{descriptor.dev_eui}:{key}"
        )
    device = device_registry.async_get_device_by_identifier(
        ("sensecap", f"network:{descriptor.dev_eui}"), config_entry.entry_id
    )
    assert device.name == "Greenhouse"
    assert device.manufacturer == "Seeed Studio"
    assert device.model == f"SenseCAP {model.__name__}"
    assert device.config_entry_id == config_entry.entry_id
    mock_connection.disconnect()
    await hass.async_block_till_done()
    for key in fixture["expected"]:
        assert hass.states.get(f"sensor.greenhouse_{key}").state == "unavailable"
    manager = config_entry.runtime_data
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert not manager.coordinators


async def test_new_devices(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    descriptor: DeviceDescriptor,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Add and remove sensors after setup, ignoring unsupported models."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert not hass.states.async_all("sensor")
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 2
    other = replace(
        descriptor,
        dev_eui="0201010101010102",
        name="Outside",
        model_id=S2102.identifiers["chirpstack"][1],
    )
    mock_connection.emit(AddedEvent(descriptor=other, received_at=dt_util.utcnow()))
    unsupported = replace(
        descriptor,
        dev_eui="0201010101010103",
        name="Unsupported",
        model_id=S2103.identifiers["chirpstack"][1],
    )
    mock_connection.emit(
        AddedEvent(descriptor=unsupported, received_at=dt_util.utcnow())
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.outside_illuminance").state == "unknown"
    assert len(hass.states.async_all("sensor")) == 3
    assert len(config_entry.runtime_data.coordinators) == 3
    assert (
        device_registry.async_get_device_by_identifier(
            ("sensecap", f"network:{unsupported.dev_eui}"), config_entry.entry_id
        )
        is None
    )
    mock_connection.emit(RemovedEvent(descriptor=other, received_at=dt_util.utcnow()))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.outside_illuminance") is None
    assert (
        device_registry.async_get_device_by_identifier(
            ("sensecap", f"network:{other.dev_eui}"), config_entry.entry_id
        )
        is None
    )
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_unload_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Keep the manager running if the platform cannot unload."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        assert not await hass.config_entries.async_unload(config_entry.entry_id)
