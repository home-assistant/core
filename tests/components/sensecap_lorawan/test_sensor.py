"""Test SenseCAP readings and device lifecycle through LoRaWAN events."""

from dataclasses import replace
from unittest.mock import patch

from lorawan_connection import (
    AddedEvent,
    DeviceDescriptor,
    RemovedEvent,
    StatusEvent,
    UplinkEvent,
)
from lorawan_connection.mock import MockConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture
from sensecap_lorawan import S2100, S2101, S2102, S2103, SenseCapDevice
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .const import CATALOG_MODELS


@pytest.mark.parametrize(("stack", "model"), CATALOG_MODELS)
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    descriptor: DeviceDescriptor,
    stack: str,
    model: type[SenseCapDevice],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Replay physical-device payloads through each official catalog identity."""
    descriptor = replace(
        descriptor,
        brand_id=model.identifiers[stack][0],
        model_id=model.identifiers[stack][1],
    )
    mock_connection.emit(
        AddedEvent(descriptor=descriptor, received_at=dt_util.utcnow())
    )
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    fixture = await async_load_json_object_fixture(
        hass, f"{model.__name__.lower()}.json", "sensecap_lorawan"
    )
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
        registered = entity_registry.async_get(entity_id)
        assert registered.unique_id.startswith(f"network:{descriptor.dev_eui}:")
    device = device_registry.async_get_device_by_identifier(
        ("sensecap_lorawan", f"network:{descriptor.dev_eui}"), config_entry.entry_id
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
    assert len(hass.states.async_all("sensor")) == 3
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
        model_id=S2100.identifiers["chirpstack"][1],
    )
    mock_connection.emit(
        AddedEvent(descriptor=unsupported, received_at=dt_util.utcnow())
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.outside_illuminance").state == "unknown"
    assert len(hass.states.async_all("sensor")) == 5
    assert len(config_entry.runtime_data.coordinators) == 3
    assert (
        device_registry.async_get_device_by_identifier(
            ("sensecap_lorawan", f"network:{unsupported.dev_eui}"),
            config_entry.entry_id,
        )
        is None
    )
    mock_connection.emit(RemovedEvent(descriptor=other, received_at=dt_util.utcnow()))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.outside_illuminance") is None
    assert (
        device_registry.async_get_device_by_identifier(
            ("sensecap_lorawan", f"network:{other.dev_eui}"), config_entry.entry_id
        )
        is None
    )
    assert await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize("stack", ["chirpstack", "tts"])
@pytest.mark.parametrize(
    ("model", "payload", "expected"),
    [
        (S2101, "000700640005000000", "100.0"),
        (S2102, "000700640005000000", "100.0"),
        (S2103, "000200e501206000030030f1f72c0007004d000500d21e", "77.0"),
    ],
    ids=["S2101", "S2102", "S2103"],
)
async def test_battery_uplink(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    descriptor: DeviceDescriptor,
    stack: str,
    model: type[S2101 | S2102 | S2103],
    payload: str,
    expected: str,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Expose battery uplinks for supported models on both catalogs."""
    descriptor = replace(descriptor, model_id=model.identifiers[stack][1])
    mock_connection.emit(
        AddedEvent(descriptor=descriptor, received_at=dt_util.utcnow())
    )
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = "sensor.greenhouse_battery"
    assert hass.states.get(entity_id).state == "unknown"
    registered = entity_registry.async_get(entity_id)
    assert registered.unique_id == f"network:{descriptor.dev_eui}:battery"
    assert registered.entity_category is EntityCategory.DIAGNOSTIC
    mock_connection.emit(
        UplinkEvent(
            descriptor=descriptor,
            received_at=dt_util.utcnow(),
            f_port=2,
            data=bytes.fromhex(payload),
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expected
    assert hass.states.get(entity_id) == snapshot
    mock_connection.disconnect()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"


@pytest.mark.parametrize("model", [S2101, S2102, S2103])
async def test_battery_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    descriptor: DeviceDescriptor,
    model: type[S2101 | S2102 | S2103],
) -> None:
    """Prefer status reports, including zero, and fall back when unavailable."""
    descriptor = replace(descriptor, model_id=model.identifiers["chirpstack"][1])
    mock_connection.emit(
        AddedEvent(descriptor=descriptor, received_at=dt_util.utcnow())
    )
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = "sensor.greenhouse_battery"
    assert hass.states.get(entity_id).state == "unknown"
    mock_connection.emit(
        StatusEvent(
            descriptor=descriptor,
            received_at=dt_util.utcnow(),
            battery_level=75.0,
            battery_level_unavailable=False,
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "75.0"
    mock_connection.emit(
        UplinkEvent(
            descriptor=descriptor,
            received_at=dt_util.utcnow(),
            f_port=2,
            data=bytes.fromhex("000700640005000000"),
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "75.0"
    mock_connection.emit(
        StatusEvent(
            descriptor=descriptor,
            received_at=dt_util.utcnow(),
            battery_level=0.0,
            battery_level_unavailable=False,
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "0.0"
    mock_connection.emit(
        StatusEvent(descriptor=descriptor, received_at=dt_util.utcnow())
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "100.0"


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


@pytest.mark.parametrize(("stack", "model"), CATALOG_MODELS)
async def test_model_battery(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    descriptor: DeviceDescriptor,
    stack: str,
    model: type[SenseCapDevice],
) -> None:
    """Every supported model exposes payload and standardized status battery data."""
    brand_id, model_id = model.identifiers[stack]
    descriptor = replace(descriptor, brand_id=brand_id, model_id=model_id)
    mock_connection.emit(AddedEvent(descriptor=descriptor))
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    fixture = await async_load_json_object_fixture(
        hass, f"{model.__name__.lower()}.json", "sensecap_lorawan"
    )
    payload = {
        1: "000700640005000000",
        2: "000700640005000000",
        3: "39640100020000050000",
    }[fixture["f_port"]]
    mock_connection.emit(
        UplinkEvent(
            descriptor=descriptor,
            received_at=dt_util.utcnow(),
            f_port=fixture["f_port"],
            data=bytes.fromhex(payload),
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.greenhouse_battery").state == "100.0"
    mock_connection.emit(
        StatusEvent(
            descriptor=descriptor,
            received_at=dt_util.utcnow(),
            battery_level=0.0,
            battery_level_unavailable=False,
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.greenhouse_battery").state == "0.0"
