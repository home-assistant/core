"""Tests for the LaCrosse sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from serial import SerialException

from homeassistant.components.lacrosse.const import DOMAIN, sensor_entity_key
from homeassistant.components.lacrosse.sensor import (
    LaCrosseBattery,
    LaCrosseHumidity,
    LaCrosseSensor,
    LaCrosseTemperature,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("mock_lacrosse")
@pytest.mark.parametrize(
    "sensor_types",
    [
        pytest.param(("temperature",), id="temperature-only"),
        pytest.param(("humidity",), id="humidity-only"),
        pytest.param(("battery",), id="battery-only"),
        pytest.param(("temperature", "humidity"), id="temperature-humidity"),
        pytest.param(("temperature", "battery"), id="temperature-battery"),
        pytest.param(("humidity", "battery"), id="humidity-battery"),
        pytest.param(("temperature", "humidity", "battery"), id="all-types"),
    ],
)
async def test_import_creates_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    sensor_types: tuple[str, ...],
) -> None:
    """Test YAML imports create every supported measurement."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            "device": "/dev/ttyUSB0",
            "baud": 57600,
            "sensors": {
                f"outdoor_{sensor_type}": {
                    "id": 1,
                    "type": sensor_type,
                    "name": "Outdoor",
                    "expire_after": 60,
                }
                for sensor_type in sensor_types
            },
        },
    )
    await hass.async_block_till_done()

    entry = result["result"]
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == 3
    assert {entity.original_name for entity in entities} == {
        "Temperature",
        "Humidity",
        "Battery",
    }
    subentry = next(iter(entry.subentries.values()))
    for sensor_type in ("temperature", "humidity", "battery"):
        entity_key = (
            f"outdoor_{sensor_type}"
            if sensor_type in sensor_types
            else sensor_entity_key(subentry.subentry_id, sensor_type)
        )
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{entity_key}"
        )
        assert entity_id is not None
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        if sensor_type in sensor_types:
            assert entity.disabled_by is None
            assert hass.states.get(entity_id) is not None
        else:
            assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
            assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("mock_lacrosse")
async def test_yaml_import(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a successful YAML import creates only the deprecation issue."""
    assert await async_setup_component(
        hass, "sensor", {"sensor": {"platform": DOMAIN, "sensors": {}}}
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_/dev/ttyUSB0"
    )


@pytest.mark.usefixtures("mock_lacrosse", "mock_setup_entry")
@pytest.mark.parametrize(
    "mock_unique_id",
    [
        pytest.param(None, id="without-unique-id"),
        pytest.param("/dev/ttyUSB0", id="with-unique-id"),
    ],
)
async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test an existing receiver still creates only the deprecation issue."""
    assert await async_setup_component(
        hass, "sensor", {"sensor": {"platform": DOMAIN, "sensors": {}}}
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [config_entry]
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_/dev/ttyUSB0"
    )


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("config", "device"),
    [
        pytest.param({}, "/dev/ttyUSB0", id="default-device"),
        pytest.param({"device": "/dev/ttyUSB1"}, "/dev/ttyUSB1", id="explicit-device"),
    ],
)
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(SerialException, id="cannot-connect"),
        pytest.param(RuntimeError, id="unexpected-error"),
    ],
)
async def test_yaml_import_failure(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    config: dict[str, str],
    device: str,
    exception: type[Exception],
) -> None:
    """Test a failed import creates only a failure issue using the YAML path."""
    with (
        patch(
            "homeassistant.components.lacrosse.config_flow.usb.get_serial_by_id",
            return_value="/dev/serial/by-id/receiver",
        ),
        patch(
            "homeassistant.components.lacrosse.config_flow.pylacrosse.LaCrosse",
            side_effect=exception("unavailable"),
        ),
    ):
        assert await async_setup_component(
            hass, "sensor", {"sensor": {"platform": DOMAIN, "sensors": {}, **config}}
        )
        await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_cannot_connect_{device}"
    )
    assert issue is not None
    assert [
        entry
        for entry in issue_registry.issues.values()
        if entry.issue_domain == DOMAIN
    ] == [issue]
    assert issue.translation_key == "deprecated_yaml_import_issue_cannot_connect"
    assert issue.translation_placeholders == {
        "device": device,
        "integration_title": "LaCrosse",
    }


async def test_yaml_import_already_in_progress(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an overlapping import creates a deprecation issue, not a failure."""
    with patch.object(
        hass.config_entries.flow,
        "async_init",
        return_value={"type": FlowResultType.ABORT, "reason": "already_in_progress"},
    ):
        assert await async_setup_component(
            hass, "sensor", {"sensor": {"platform": DOMAIN, "sensors": {}}}
        )
        await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_/dev/ttyUSB0"
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_yaml_import_multiple_failures(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test failed imports for different receivers create separate issues."""
    with patch(
        "homeassistant.components.lacrosse.config_flow.pylacrosse.LaCrosse",
        side_effect=SerialException("unavailable"),
    ):
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": [
                    {"platform": DOMAIN, "device": "/dev/ttyUSB0", "sensors": {}},
                    {"platform": DOMAIN, "device": "/dev/ttyUSB1", "sensors": {}},
                ]
            },
        )
        await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_/dev/ttyUSB0"
    )
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_/dev/ttyUSB1"
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_yaml_import_mixed_outcomes(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a successful receiver and a failed receiver retain their own issues."""
    receivers = {"/dev/ttyUSB0": MagicMock(), "/dev/ttyUSB1": MagicMock()}
    receivers["/dev/ttyUSB1"].open.side_effect = SerialException("unavailable")
    with (
        patch(
            "homeassistant.components.lacrosse.config_flow.usb.get_serial_by_id",
            side_effect=lambda device: device,
        ),
        patch(
            "homeassistant.components.lacrosse.config_flow.pylacrosse.LaCrosse",
            side_effect=lambda device, baud: receivers[device],
        ),
    ):
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": [
                    {"platform": DOMAIN, "device": "/dev/ttyUSB0", "sensors": {}},
                    {"platform": DOMAIN, "device": "/dev/ttyUSB1", "sensors": {}},
                ]
            },
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_/dev/ttyUSB1"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_/dev/ttyUSB0"
    )


@pytest.mark.usefixtures("mock_lacrosse")
async def test_sensor_name_includes_sensor_type(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a friendly name is combined with the sensor type."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{config_entry.entry_id}_{sensor_entity_key('sensor_1', 'humidity')}",
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["friendly_name"] == "Outdoor Humidity"


@pytest.mark.parametrize(
    ("config", "device_name", "object_id"),
    [
        pytest.param(
            {"id": 1, "name": "Outdoor Patio"},
            "Outdoor Patio",
            "outdoor_patio",
            id="friendly-name",
        ),
        pytest.param(
            {"id": 1, "name": "  Outdoor-PATIO  "},
            "  Outdoor-PATIO  ",
            "outdoor_patio",
            id="formatted-name",
        ),
        pytest.param({"id": 2}, "LaCrosse sensor 2", "2", id="sensor-id-fallback"),
        pytest.param(
            {"id": 2, "name": ""},
            "LaCrosse sensor 2",
            "2",
            id="empty-name-fallback",
        ),
        pytest.param(
            {"id": 2, "name": "   "},
            "LaCrosse sensor 2",
            "2",
            id="blank-name-fallback",
        ),
    ],
)
@pytest.mark.parametrize("sensor_type", ["temperature", "humidity", "battery"])
def test_device_uses_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config: dict[str, str | int],
    device_name: str,
    object_id: str,
    sensor_type: str,
) -> None:
    """Test the entity ID is generated from the configured sensor key."""
    sensor_class = {
        "temperature": LaCrosseTemperature,
        "humidity": LaCrosseHumidity,
        "battery": LaCrosseBattery,
    }[sensor_type]
    sensor = sensor_class(
        hass,
        MagicMock(),
        mock_config_entry.entry_id,
        mock_config_entry.data["device"],
        f"{object_id}_{sensor_type}",
        device_name,
        None,
        config,
    )

    assert sensor.device_info.name == device_name
    assert sensor.entity_id == f"sensor.{object_id}_{sensor_type}"


async def test_temperature_and_humidity_sensor_values(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test temperature and humidity sensor values update from the receiver."""
    receiver = MagicMock()
    sensor_data = MagicMock(
        temperature=21.5, humidity=54, low_battery=False, new_battery=True
    )
    config = dict(mock_config_entry.subentries["sensor_1"].data)
    temperature = LaCrosseTemperature(
        hass,
        receiver,
        mock_config_entry.entry_id,
        mock_config_entry.data["device"],
        "outdoor_temperature",
        "Outdoor temperature",
        None,
        config,
    )
    humidity = LaCrosseHumidity(
        hass,
        receiver,
        mock_config_entry.entry_id,
        mock_config_entry.data["device"],
        "outdoor_humidity",
        "Outdoor humidity",
        None,
        config,
    )

    temperature._callback_lacrosse(sensor_data, None)
    humidity._callback_lacrosse(sensor_data, None)

    assert temperature.native_value == 21.5
    assert humidity.native_value == 54
    assert temperature.extra_state_attributes == {
        "low_battery": False,
        "new_battery": True,
    }


def test_sensor_registers_callback_when_created(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test receiver callbacks are registered when the entity is created."""
    receiver = MagicMock()
    sensor = LaCrosseSensor(
        hass,
        receiver,
        mock_config_entry.entry_id,
        mock_config_entry.data["device"],
        "outdoor_temperature",
        "Outdoor temperature",
        None,
        dict(mock_config_entry.subentries["sensor_1"].data),
    )

    assert sensor.should_poll is True
    receiver.register_callback.assert_called_once_with(
        1, sensor._callback_lacrosse, None
    )


async def test_sensor_cancels_expiration_when_removed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the expiration trigger is cancelled when the entity is removed."""
    sensor = LaCrosseSensor(
        hass,
        MagicMock(),
        mock_config_entry.entry_id,
        mock_config_entry.data["device"],
        "outdoor_temperature",
        "Outdoor temperature",
        30,
        dict(mock_config_entry.subentries["sensor_1"].data),
    )
    expiration_trigger = MagicMock()
    sensor._expiration_trigger = expiration_trigger

    await sensor.async_will_remove_from_hass()

    expiration_trigger.assert_called_once()
    assert sensor._expiration_trigger is None


@pytest.mark.parametrize(
    ("low_battery", "new_battery", "expected_value", "expected_icon"),
    [
        pytest.param(False, True, "ok", "mdi:battery", id="new"),
        pytest.param(False, False, "ok", "mdi:battery", id="ok"),
        pytest.param(True, False, "low", "mdi:battery-alert", id="low"),
    ],
)
async def test_battery_sensor_updates_and_expires(
    hass: HomeAssistant,
    low_battery: bool,
    new_battery: bool,
    expected_value: str,
    expected_icon: str,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test battery values, icons, and expiration scheduling."""
    receiver = MagicMock()
    sensor = LaCrosseBattery(
        hass,
        receiver,
        mock_config_entry.entry_id,
        mock_config_entry.data["device"],
        "outdoor_battery",
        "Outdoor battery",
        30,
        dict(mock_config_entry.subentries["sensor_1"].data),
    )
    expiration_trigger = MagicMock()
    sensor_data = MagicMock(
        temperature=21.5,
        humidity=54,
        low_battery=low_battery,
        new_battery=new_battery,
    )

    assert sensor.native_value is None
    assert sensor.icon == "mdi:battery-unknown"

    with (
        patch(
            "homeassistant.components.lacrosse.sensor.async_track_point_in_utc_time",
            return_value=expiration_trigger,
        ) as mock_track_expiration,
    ):
        sensor._callback_lacrosse(sensor_data, None)
        sensor._callback_lacrosse(sensor_data, None)

    assert mock_track_expiration.call_count == 2
    expiration_trigger.assert_called_once()
    assert sensor.native_value == expected_value
    assert sensor.icon == expected_icon

    with patch.object(sensor, "async_write_ha_state") as mock_write_state:
        sensor.value_is_expired()

    assert sensor._expiration_trigger is None
    assert sensor.native_value == expected_value
    assert sensor.icon == expected_icon
    mock_write_state.assert_called_once()
