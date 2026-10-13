"""Tests for the LaCrosse config flow."""

from types import MappingProxyType
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from serial import SerialException

from homeassistant import config_entries
from homeassistant.components.lacrosse.config_flow import sensor_subentries
from homeassistant.components.lacrosse.const import (
    DOMAIN,
    LaCrosseSensorType,
    sensor_entity_key,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from tests.common import MockConfigEntry

RECEIVER_DATA = {"device": "/dev/ttyUSB0", "baud": 57600}
TEMPERATURE_SENSOR = {
    "id": 1,
    "temperature": True,
    "humidity": False,
    "battery": False,
    "expire_after": 300,
    "friendly_name": "Outdoor",
}
SENSORS = {
    "1_temperature": {
        "id": 1,
        "type": "temperature",
        "expire_after": 300,
        "friendly_name": "Outdoor",
        "unique_id": "temperature_unique",
    },
    "1_humidity": {
        "id": 1,
        "type": "humidity",
        "friendly_name": "Outdoor",
        "unique_id": "humidity_unique",
    },
    "2_temperature": {"id": 2, "type": "temperature", "unique_id": "bedroom_unique"},
}

pytestmark = pytest.mark.usefixtures("mock_lacrosse", "mock_setup_entry")


@pytest.mark.parametrize(
    ("sensor_id", "sensor_type", "friendly_name", "expected_key"),
    [
        pytest.param(
            1,
            LaCrosseSensorType.TEMPERATURE,
            "Outdoor Patio",
            "outdoor_patio_temperature",
            id="friendly-name",
        ),
        pytest.param(
            2,
            LaCrosseSensorType.HUMIDITY,
            None,
            "2_humidity",
            id="sensor-id-fallback",
        ),
    ],
)
def test_sensor_entity_key(
    sensor_id: int,
    sensor_type: LaCrosseSensorType,
    friendly_name: str | None,
    expected_key: str,
) -> None:
    """Test sensor keys use the friendly name or sensor ID and sensor type."""
    assert sensor_entity_key(sensor_id, sensor_type, friendly_name) == expected_key


def test_sensor_subentries_empty_friendly_name_uses_sensor_id() -> None:
    """Test an empty friendly name falls back to the generated subentry title."""
    subentries = sensor_subentries({"1_temperature": {"id": 1, "friendly_name": ""}})

    assert subentries[0]["title"] == "LaCrosse sensor 1"


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a hub with two physical sensor subentries."""
    entry = MockConfigEntry(domain=DOMAIN, data=RECEIVER_DATA)
    entry.add_to_hass(hass)
    for subentry_data in sensor_subentries(SENSORS):
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
    """Test configuring a receiver and multiple types of one sensor."""
    with patch(
        "homeassistant.components.lacrosse.config_flow.uuid4",
        side_effect=[UUID(int=1), UUID(int=2)],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**RECEIVER_DATA, "frequency": frequency}
        )
        assert result["step_id"] == "add_sensor"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEMPERATURE_SENSOR
        )
        assert result["step_id"] == "add_sensor_or_finish"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "add_sensor"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**TEMPERATURE_SENSOR, "temperature": False, "humidity": True},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "finish"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**RECEIVER_DATA, "frequency": expected_frequency}
    assert type(result["data"]["frequency"]) is int
    entry = result["result"]
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.unique_id == "1"
    assert subentry.title == "Outdoor"
    assert subentry.data["sensors"] == {
        "outdoor_temperature": {
            **SENSORS["1_temperature"],
            "unique_id": UUID(int=1).hex,
        },
        "outdoor_humidity": {
            **SENSORS["1_humidity"],
            "expire_after": 300,
            "unique_id": UUID(int=2).hex,
        },
    }
    mock_setup_entry.assert_called_once()


async def test_user_flow_same_friendly_name_and_type_keeps_both_sensors(
    hass: HomeAssistant,
) -> None:
    """Test sensors with colliding friendly-name keys are both retained."""
    first_sensor = {**TEMPERATURE_SENSOR, "id": 3, "friendly_name": "Shared"}
    second_sensor = {**TEMPERATURE_SENSOR, "id": 4, "friendly_name": "Shared"}
    third_sensor = {**TEMPERATURE_SENSOR, "id": 5, "friendly_name": "Shared"}
    assert (
        sensor_entity_key(first_sensor["id"], LaCrosseSensorType.TEMPERATURE, "Shared")
        == sensor_entity_key(
            second_sensor["id"], LaCrosseSensorType.TEMPERATURE, "Shared"
        )
        == sensor_entity_key(
            third_sensor["id"], LaCrosseSensorType.TEMPERATURE, "Shared"
        )
    )

    with patch(
        "homeassistant.components.lacrosse.config_flow.uuid4",
        side_effect=[UUID(int=1), UUID(int=2), UUID(int=3)],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=RECEIVER_DATA
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], first_sensor
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "add_sensor"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], second_sensor
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "add_sensor"}
        )
        flow = hass.config_entries.flow._progress[result["flow_id"]]
        flow._sensors["shared_temperature_5"] = {
            "id": 6,
            "type": "temperature",
            "friendly_name": "Occupied key",
            "unique_id": "occupied_key_unique",
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], third_sensor
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "finish"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert {subentry.unique_id for subentry in entry.subentries.values()} == {
        "3",
        "4",
        "5",
        "6",
    }
    configured_sensors = [
        (key, sensor)
        for subentry in entry.subentries.values()
        for key, sensor in subentry.data["sensors"].items()
    ]
    assert {sensor["id"] for _, sensor in configured_sensors} == {3, 4, 5, 6}
    assert len({key for key, _ in configured_sensors}) == 4
    assert any(
        key == "shared_temperature_5_2" and sensor["id"] == 5
        for key, sensor in configured_sensors
    )


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
    assert result["step_id"] == "add_sensor"
    assert not result["errors"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEMPERATURE_SENSOR
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_receiver(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a receiver can only be configured once."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=RECEIVER_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test grouping YAML entities into physical sensor subentries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            **RECEIVER_DATA,
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
    assert result["data"]["frequency"] == 868300
    assert type(result["data"]["frequency"]) is int
    assert "sensors" not in result["data"]
    entry = result["result"]
    assert {subentry.unique_id for subentry in entry.subentries.values()} == {"34", "9"}
    heating = next(
        subentry for subentry in entry.subentries.values() if subentry.unique_id == "34"
    )
    assert set(heating.data["sensors"]) == {"heating", "heating_temperature"}
    assert heating.data["sensors"]["heating"]["friendly_name"] == "heating"
    assert heating.data["sensors"]["heating_temperature"]["friendly_name"] == "Heating"
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("sensor_input", "error"),
    [
        pytest.param(TEMPERATURE_SENSOR, "sensor_already_configured", id="duplicate"),
        pytest.param(
            {**TEMPERATURE_SENSOR, "id": 3, "temperature": False, "battery": True},
            "value_type_required",
            id="battery-only",
        ),
    ],
)
async def test_initial_sensor_validation(
    hass: HomeAssistant, sensor_input: dict[str, object], error: str
) -> None:
    """Test invalid sensor configurations and subsequent recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=RECEIVER_DATA
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEMPERATURE_SENSOR
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_sensor"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], sensor_input
    )
    assert result["errors"] == {"base": error}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TEMPERATURE_SENSOR, "id": 4}
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("receiver_device", ["/dev/ttyUSB0", "/dev/manual_receiver"])
@pytest.mark.parametrize(
    ("frequency_input", "expected_data"),
    [
        pytest.param(
            "",
            {"device": "/dev/ttyUSB1", "baud": 38400},
            id="clear-frequency",
        ),
        pytest.param(
            868.305,
            {"device": "/dev/ttyUSB1", "baud": 38400, "frequency": 868305},
            id="update-frequency",
        ),
    ],
)
async def test_update_receiver(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    receiver_device: str,
    frequency_input: float | str,
    expected_data: dict[str, str | int],
) -> None:
    """Test receiver-only reconfiguration preserves sensor subentries."""
    hass.config_entries.async_update_entry(
        config_entry,
        data={**RECEIVER_DATA, "device": receiver_device, "frequency": 868300},
    )
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id="sensor_1",
        identifiers={(DOMAIN, f"{receiver_device}_1")},
    )
    subentries = dict(config_entry.subentries)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "update_receiver"
    device_field = next(
        field for field in result["data_schema"].schema if field == "device"
    )
    assert device_field.description == {"suggested_value": receiver_device}
    frequency_field = next(
        field for field in result["data_schema"].schema if field == "frequency"
    )
    assert frequency_field.description == {"suggested_value": 868.3}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device": "/dev/ttyUSB1", "baud": 38400, "frequency": frequency_input},
    )
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == expected_data
    assert config_entry.subentries == subentries
    assert device_registry.async_get(device.id).identifiers == {
        (DOMAIN, "/dev/ttyUSB1_1")
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [(SerialException, "cannot_connect"), (RuntimeError, "unknown")],
)
async def test_update_receiver_invalid_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    exception: type[Exception],
    error: str,
) -> None:
    """Test receiver errors leave the hub unchanged and allow a retry."""
    result = await config_entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.lacrosse.config_flow.pylacrosse.LaCrosse",
        side_effect=exception("unavailable"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB1", "baud": 38400}
        )
    assert result["errors"] == {"base": error}
    assert config_entry.data == RECEIVER_DATA
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECEIVER_DATA
    )
    assert result["reason"] == "reconfigure_successful"


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
    )
    device_registry.async_update_device(device.id, name_by_user="My sensor")
    temperature = subentry.data["sensors"][f"{sensor_id}_temperature"]
    entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        temperature["unique_id"],
        config_entry=config_entry,
        config_subentry_id=subentry.subentry_id,
        device_id=device.id,
    )
    entity_registry.async_update_entity(entity.entity_id, name="My temperature")
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    suggestions = {
        key.schema: key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggestions["id"] == sensor_id
    assert suggestions["temperature"] is True
    assert suggestions["humidity"] == (sensor_id == 1)
    assert suggestions["battery"] is False
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"id": 7, "temperature": True, "humidity": sensor_id == 1, "battery": True},
    )
    assert result["reason"] == "reconfigure_successful"
    assert subentry.unique_id == "7"
    assert (
        subentry.data["sensors"]["7_temperature"]["unique_id"]
        == temperature["unique_id"]
    )
    assert UUID(subentry.data["sensors"]["7_battery"]["unique_id"])
    assert "friendly_name" not in subentry.data["sensors"]["7_temperature"]
    updated_device = device_registry.async_get(device.id)
    assert updated_device.identifiers == {(DOMAIN, "/dev/ttyUSB0_7")}
    assert updated_device.name_by_user == "My sensor"
    assert updated_device.model == "Sensor ID 7"
    assert entity_registry.async_get(entity.entity_id).name == "My temperature"


@pytest.mark.parametrize(
    ("user_input", "error"),
    [
        pytest.param(
            {**TEMPERATURE_SENSOR, "id": 2}, "sensor_already_configured", id="duplicate"
        ),
        pytest.param(
            {**TEMPERATURE_SENSOR, "temperature": False, "battery": True},
            "value_type_required",
            id="battery-only",
        ),
    ],
)
async def test_update_sensor_validation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    user_input: dict[str, object],
    error: str,
) -> None:
    """Test invalid updates leave the subentry unchanged and allow recovery."""
    subentry = config_entry.subentries["sensor_1"]
    original = dict(subentry.data)
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input
    )
    assert result["errors"] == {"base": error}
    assert subentry.data == original
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], TEMPERATURE_SENSOR
    )
    assert result["reason"] == "reconfigure_successful"


async def test_update_sensor_remove_type(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test deselecting a type removes its entity registry entry."""
    humidity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "humidity_unique",
        config_entry=config_entry,
        config_subentry_id="sensor_1",
    )
    result = await config_entry.start_subentry_reconfigure_flow(hass, "sensor_1")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], TEMPERATURE_SENSOR
    )
    assert result["reason"] == "reconfigure_successful"
    assert set(config_entry.subentries["sensor_1"].data["sensors"]) == {
        "outdoor_temperature"
    }
    assert entity_registry.async_get(humidity.entity_id) is None


async def test_add_sensor(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test Add Sensor creates a device subentry under the selected hub."""
    original = dict(config_entry.subentries)
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**TEMPERATURE_SENSOR, "id": 3, "humidity": True, "battery": True},
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
    assert set(subentry.data["sensors"]) == {
        "outdoor_temperature",
        "outdoor_humidity",
        "outdoor_battery",
    }
    assert (
        len({sensor["unique_id"] for sensor in subentry.data["sensors"].values()}) == 3
    )
    assert {key: config_entry.subentries[key] for key in original} == original


@pytest.mark.parametrize(
    ("user_input", "error"),
    [
        pytest.param(TEMPERATURE_SENSOR, "sensor_already_configured", id="duplicate"),
        pytest.param(
            {**TEMPERATURE_SENSOR, "id": 3, "temperature": False, "battery": True},
            "value_type_required",
            id="battery-only",
        ),
    ],
)
async def test_add_sensor_validation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    user_input: dict[str, object],
    error: str,
) -> None:
    """Test adding a sensor rejects invalid input and permits recovery."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input
    )
    assert result["errors"] == {"base": error}
    assert len(config_entry.subentries) == 2
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**TEMPERATURE_SENSOR, "id": 3}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(config_entry.subentries) == 3
