"""Tests for the LaCrosse config flow."""

import asyncio
from threading import Event
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
from serial import SerialException

from homeassistant import config_entries
from homeassistant.components.lacrosse.config_flow import sensor_subentries
from homeassistant.components.lacrosse.const import (
    CONF_LEGACY_CONFIGURED_TYPES,
    CONF_LEGACY_ENTITY_KEYS,
    DOMAIN,
    sensor_entity_key,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

RECEIVER_DATA = {"device": "/dev/ttyUSB0", "baud": 57600}
TEMPERATURE_SENSOR = {
    "id": 1,
    "name": "Outdoor",
}
pytestmark = pytest.mark.usefixtures("mock_lacrosse", "mock_setup_entry")


@pytest.mark.parametrize(
    ("subentry_id", "sensor_type", "expected_key"),
    [
        pytest.param("01ABC", "temperature", "01ABC_temperature", id="temperature"),
        pytest.param("01ABC", "humidity", "01ABC_humidity", id="humidity"),
    ],
)
def test_sensor_entity_key(
    subentry_id: str,
    sensor_type: str,
    expected_key: str,
) -> None:
    """Test sensor keys use the sensor ID and type, not the friendly name."""
    assert sensor_entity_key(subentry_id, sensor_type) == expected_key


def test_sensor_subentries_empty_name_uses_sensor_id() -> None:
    """Test an empty friendly name falls back to the generated subentry title."""
    subentries = sensor_subentries(
        {"1_temperature": {"id": 1, "type": "temperature", "name": ""}}
    )

    assert subentries[0]["title"] == "LaCrosse sensor 1"


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a hub with two ID/name sensor subentries."""
    entry = MockConfigEntry(domain=DOMAIN, data=RECEIVER_DATA)
    entry.add_to_hass(hass)
    for sensor_id, name in ((1, "Outdoor"), (2, "LaCrosse sensor 2")):
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType({"id": sensor_id, "name": name}),
                subentry_type="sensor",
                title=name,
                unique_id=str(sensor_id),
                subentry_id=f"sensor_{sensor_id}",
            ),
        )
    return entry


@pytest.mark.parametrize(
    ("frequency", "expected_frequency"),
    [
        pytest.param(868.3, 868300, id="decimal-mhz"),
        pytest.param("868.3", 868300, id="string-mhz"),
        pytest.param(868.305, 868305, id="three-decimal-mhz"),
    ],
)
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    frequency: float | str,
    expected_frequency: int,
) -> None:
    """Test configuring a receiver creates an entry without sensor subentries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**RECEIVER_DATA, "frequency": frequency}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**RECEIVER_DATA, "frequency": expected_frequency}
    assert type(result["data"]["frequency"]) is int
    entry = result["result"]
    assert entry.unique_id == RECEIVER_DATA["device"]
    assert not entry.subentries
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    "sensor_ids",
    [
        pytest.param((4, 5), id="multiple-sensors"),
        pytest.param((4,), id="single-sensor"),
    ],
)
async def test_add_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sensor_ids: tuple[int, ...],
) -> None:
    """Test adding a physical sensor stores only its ID and name."""
    original = dict(config_entry.subentries)
    for sensor_id in sensor_ids:
        result = await hass.config_entries.subentries.async_init(
            (config_entry.entry_id, "sensor"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"id": sensor_id, "name": "Shared"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
    new_subentries = [
        subentry
        for subentry_id, subentry in config_entry.subentries.items()
        if subentry_id not in original
    ]
    assert [subentry.data for subentry in new_subentries] == [
        {"id": sensor_id, "name": "Shared"} for sensor_id in sensor_ids
    ]
    assert {key: config_entry.subentries[key] for key in original} == original


@pytest.mark.parametrize(
    ("exception", "error"),
    [(SerialException, "cannot_connect"), (RuntimeError, "unknown")],
)
async def test_user_flow_receiver_error(
    hass: HomeAssistant, exception: type[Exception], error: str
) -> None:
    """Test recovery from a receiver connection failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.lacrosse.config_flow.pylacrosse.LaCrosse",
        side_effect=exception("unavailable"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], RECEIVER_DATA
        )
    assert result["errors"] == {"base": error}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECEIVER_DATA
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_receiver(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a receiver can only be configured once."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECEIVER_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("first_source", "second_source"),
    [
        pytest.param(
            config_entries.SOURCE_USER, config_entries.SOURCE_USER, id="user-user"
        ),
        pytest.param(
            config_entries.SOURCE_USER, config_entries.SOURCE_IMPORT, id="user-import"
        ),
        pytest.param(
            config_entries.SOURCE_IMPORT, config_entries.SOURCE_USER, id="import-user"
        ),
    ],
)
async def test_overlapping_receiver_flows(
    hass: HomeAssistant, first_source: str, second_source: str
) -> None:
    """Test overlapping flows reserve the resolved receiver before opening it."""
    validation_started = asyncio.Event()
    validation_release = Event()
    resolved_device = "/dev/serial/by-id/receiver"

    def open_receiver() -> None:
        hass.loop.call_soon_threadsafe(validation_started.set)
        assert validation_release.wait(timeout=10)

    with (
        patch(
            "homeassistant.components.lacrosse.config_flow.usb.get_serial_by_id",
            return_value=resolved_device,
        ),
        patch(
            "homeassistant.components.lacrosse.config_flow.pylacrosse.LaCrosse.return_value.open",
            side_effect=open_receiver,
        ) as mock_open,
    ):
        first_flow = hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": first_source},
                data=dict(RECEIVER_DATA),
            )
        )
        try:
            await validation_started.wait()
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": second_source},
                data={**RECEIVER_DATA, "device": "/dev/ttyUSB1"},
            )
            assert result["type"] is FlowResultType.ABORT
            assert result["reason"] == "already_in_progress"
            mock_open.assert_called_once()
        finally:
            validation_release.set()
            first_result = await first_flow

    assert first_result["type"] is FlowResultType.CREATE_ENTRY
    assert first_result["result"].unique_id == resolved_device
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    ("receiver_data", "expected_device"),
    [
        pytest.param({"baud": 57600}, "/dev/ttyUSB0", id="default-device"),
        pytest.param(
            {"device": "/dev/ttyUSB1", "baud": 57600},
            "/dev/ttyUSB1",
            id="explicit-device",
        ),
    ],
)
async def test_import_flow(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    receiver_data: dict[str, str | int],
    expected_device: str,
) -> None:
    """Test grouping YAML entities into physical sensor subentries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            **receiver_data,
            "frequency": 868300,
            "sensors": {
                "heating": {"id": 34, "type": "humidity"},
                "heating_temperature": {
                    "id": 34,
                    "type": "temperature",
                    "name": "Heating",
                },
                "livingroom": {"id": 9, "type": "temperature"},
            },
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["device"] == expected_device
    assert result["data"]["frequency"] == 868300
    assert type(result["data"]["frequency"]) is int
    assert "sensors" not in result["data"]
    entry = result["result"]
    assert entry.unique_id == expected_device
    assert {subentry.unique_id for subentry in entry.subentries.values()} == {"34", "9"}
    heating = next(
        subentry for subentry in entry.subentries.values() if subentry.unique_id == "34"
    )
    assert heating.data == {
        "id": 34,
        "name": "heating",
        CONF_LEGACY_CONFIGURED_TYPES: ["humidity", "temperature"],
        CONF_LEGACY_ENTITY_KEYS: {
            "humidity": ["heating"],
            "temperature": ["heating_temperature"],
        },
    }
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(SerialException, "cannot_connect", id="cannot-connect"),
        pytest.param(RuntimeError, "unknown", id="unexpected-error"),
    ],
)
async def test_import_flow_receiver_error(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_setup_entry: AsyncMock,
    exception: type[Exception],
    reason: str,
) -> None:
    """Test failed YAML imports create a repair issue without creating an entry."""
    with patch(
        "homeassistant.components.lacrosse.config_flow.pylacrosse.LaCrosse.return_value.open",
        side_effect=exception("unavailable"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=RECEIVER_DATA,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert not hass.config_entries.async_entries(DOMAIN)
    mock_setup_entry.assert_not_called()
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml_import_issue_cannot_connect"
    assert issue.translation_placeholders == {
        "device": RECEIVER_DATA["device"],
        "integration_title": "LaCrosse",
    }


@pytest.mark.parametrize(
    "sensor_id", [pytest.param(1, id="named"), pytest.param(2, id="unnamed")]
)
async def test_update_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    sensor_id: int,
) -> None:
    """Test preselection and preservation of device and entity customizations."""
    subentry = config_entry.subentries[f"sensor_{sensor_id}"]
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id=subentry.subentry_id,
        identifiers={(DOMAIN, f"/dev/ttyUSB0_{sensor_id}")},
        name=subentry.title,
    )
    device_registry.async_update_device(device.id, name_by_user="My sensor")
    entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{config_entry.entry_id}_{sensor_entity_key(f'sensor_{sensor_id}', 'temperature')}",
        config_entry=config_entry,
        config_subentry_id=subentry.subentry_id,
        device_id=device.id,
    )
    entity_registry.async_update_entity(
        entity.entity_id,
        name="My temperature",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    original_data = dict(subentry.data)
    original_title = subentry.title
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert {key.schema for key in result["data_schema"].schema} == {"id"}
    suggestions = {
        key.schema: key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggestions["id"] == sensor_id
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"id": 7},
    )
    assert result["reason"] == "reconfigure_successful"
    assert subentry.unique_id == "7"
    assert subentry.title == original_title
    assert subentry.data == {**original_data, "id": 7}
    updated_device = device_registry.async_get(device.id)
    assert updated_device.identifiers == {(DOMAIN, "/dev/ttyUSB0_7")}
    assert updated_device.name_by_user == "My sensor"
    assert updated_device.name == original_title
    assert updated_device.model == "Sensor ID 7"
    assert entity_registry.async_get(entity.entity_id).name == "My temperature"
    assert (
        entity_registry.async_get(entity.entity_id).disabled_by
        is er.RegistryEntryDisabler.USER
    )


async def test_update_sensor_validation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test invalid updates leave the subentry unchanged and allow recovery."""
    subentry = config_entry.subentries["sensor_1"]
    original = dict(subentry.data)
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"id": 2}
    )
    assert result["errors"] == {"base": "sensor_already_configured"}
    assert subentry.data == original
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"id": 1}
    )
    assert result["reason"] == "reconfigure_successful"


async def test_update_sensor_preserves_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test updating the ID leaves every entity registry entry unchanged."""
    temperature = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{config_entry.entry_id}_{sensor_entity_key('sensor_1', 'temperature')}",
        config_entry=config_entry,
        config_subentry_id="sensor_1",
    )
    humidity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{config_entry.entry_id}_{sensor_entity_key('sensor_1', 'humidity')}",
        config_entry=config_entry,
        config_subentry_id="sensor_1",
    )
    result = await config_entry.start_subentry_reconfigure_flow(hass, "sensor_1")
    original = dict(config_entry.subentries["sensor_1"].data)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"id": 7}
    )
    assert result["reason"] == "reconfigure_successful"
    assert dict(config_entry.subentries["sensor_1"].data) == {
        **original,
        "id": 7,
    }
    assert entity_registry.async_get(humidity.entity_id) == humidity
    assert entity_registry.async_get(temperature.entity_id) == temperature


@pytest.mark.parametrize(
    ("sensor_id", "new_id"),
    [
        pytest.param(1, 7, id="named-sensor-id-changes"),
        pytest.param(2, 7, id="unnamed-sensor-id-changes"),
    ],
)
async def test_update_sensor_preserves_entity_keys(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    sensor_id: int,
    new_id: int,
) -> None:
    """Test retained keys remain stable when the sensor ID changes."""
    subentry = config_entry.subentries[f"sensor_{sensor_id}"]
    original = dict(subentry.data)
    entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{config_entry.entry_id}_{sensor_entity_key(f'sensor_{sensor_id}', 'temperature')}",
        config_entry=config_entry,
        config_subentry_id=subentry.subentry_id,
    )
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"id": new_id},
    )

    assert result["reason"] == "reconfigure_successful"
    assert subentry.data == {**original, "id": new_id}
    assert entity_registry.async_get(entity.entity_id) == entity


async def test_imported_sensor_stores_configured_entity_keys(
    hass: HomeAssistant,
) -> None:
    """Test completing an imported sensor avoids existing YAML entity keys."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=RECEIVER_DATA,
        source=config_entries.SOURCE_IMPORT,
    )
    entry.add_to_hass(hass)
    imported_sensors = {
        "temperature": {"id": 1, "type": "temperature", "name": "temperature"},
        "humidity": {"id": 1, "type": "battery", "name": "humidity"},
        "1_humidity": {"id": 2, "type": "temperature", "name": "1_humidity"},
    }
    for subentry_data in sensor_subentries(imported_sensors):
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(subentry_data["data"]),
                subentry_type="sensor",
                title=subentry_data["title"],
                unique_id=subentry_data["unique_id"],
                subentry_id=f"sensor_{subentry_data['unique_id']}",
            ),
        )

    subentry = entry.subentries["sensor_1"]
    result = await entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"id": 7},
    )

    assert result["reason"] == "reconfigure_successful"
    assert dict(subentry.data) == {
        "id": 7,
        "name": "temperature",
        CONF_LEGACY_CONFIGURED_TYPES: ["battery", "temperature"],
        CONF_LEGACY_ENTITY_KEYS: {
            "temperature": ["temperature"],
            "battery": ["humidity"],
        },
    }


async def test_update_sensor_new_type_unique_key(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test updating a sensor does not modify another sensor's configuration."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**TEMPERATURE_SENSOR, "id": 3},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    other_subentry = next(
        subentry
        for subentry in config_entry.subentries.values()
        if subentry.unique_id == "3"
    )
    original_data = dict(other_subentry.data)
    original_sensor_data = dict(config_entry.subentries["sensor_1"].data)

    result = await config_entry.start_subentry_reconfigure_flow(hass, "sensor_1")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"id": 7},
    )

    assert result["reason"] == "reconfigure_successful"
    assert dict(config_entry.subentries["sensor_1"].data) == {
        **original_sensor_data,
        "id": 7,
    }
    assert dict(other_subentry.data) == original_data


async def test_add_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test Add Sensor creates a device subentry under the selected hub."""
    original = dict(config_entry.subentries)
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    fields = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    assert {field["name"] for field in fields} == {"id", "name"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**TEMPERATURE_SENSOR, "id": 3},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data == RECEIVER_DATA
    assert len(config_entry.subentries) == 3
    subentry = next(
        subentry
        for subentry in config_entry.subentries.values()
        if subentry.unique_id == "3"
    )
    assert subentry.unique_id == "3"
    assert subentry.title == "Outdoor"
    assert subentry.data == {"id": 3, "name": "Outdoor"}
    assert {key: config_entry.subentries[key] for key in original} == original


async def test_add_multiple_sensors_to_imported_entry_stores_id_and_name(
    hass: HomeAssistant,
) -> None:
    """Test UI-created subentries on imported entries keep canonical type keys."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=RECEIVER_DATA,
        source=config_entries.SOURCE_IMPORT,
    )
    entry.add_to_hass(hass)

    for sensor_id in (3, 4):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "sensor"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                **TEMPERATURE_SENSOR,
                "id": sensor_id,
                "name": "Outdoor",
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

    assert {
        subentry.unique_id: dict(subentry.data)
        for subentry in entry.subentries.values()
    } == {
        "3": {"id": 3, "name": "Outdoor"},
        "4": {"id": 4, "name": "Outdoor"},
    }


async def test_add_sensor_validation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test adding a sensor rejects invalid input and permits recovery."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], TEMPERATURE_SENSOR
    )
    assert result["errors"] == {"base": "sensor_already_configured"}
    assert len(config_entry.subentries) == 2
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**TEMPERATURE_SENSOR, "id": 3}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(config_entry.subentries) == 3
