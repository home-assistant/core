"""Test the De Dietrich setup."""

from collections.abc import Callable
from unittest.mock import patch

import diematic_modbus
from diematic_modbus import UpdateReport
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.de_dietrich.const import DEFAULT_UNIT_ID, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    MOCK_ENTRY_ID,
    MOCK_TITLE,
    MOCK_USER_INPUT,
    seed_boiler,
    seed_isystem_boiler,
)

from tests.common import MockConfigEntry


async def test_setup_retry_when_identity_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test setup is retried when the boiler identity cannot be read."""
    mock_connection.for_unit(DEFAULT_UNIT_ID).fail_read(457, ModbusTimeoutError("boom"))
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_when_detection_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test setup is retried when detection cannot reach the boiler."""
    mock_connection.for_unit(DEFAULT_UNIT_ID).fail_requests(ModbusTimeoutError("boom"))
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_when_detection_raises_modbus_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test setup is retried when detection raises a Modbus error."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.de_dietrich.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
                unit_id
            ),
        ),
        patch(
            "homeassistant.components.de_dietrich.diematic_modbus.async_detect",
            side_effect=ModbusTimeoutError("boom"),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_when_coordinator_identity_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test setup retries when the coordinator cannot read the identity."""
    unit = mock_connection.for_unit(DEFAULT_UNIT_ID)
    detection = await diematic_modbus.async_detect(unit)
    unit.fail_read(679, ModbusTimeoutError("identity unavailable"))
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.de_dietrich.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
                unit_id
            ),
        ),
        patch(
            "homeassistant.components.de_dietrich.diematic_modbus.async_detect",
            return_value=detection,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "failed",
    [
        pytest.param({}, id="no_error_details"),
        pytest.param(
            {"sensors": ModbusTimeoutError("component unavailable")},
            id="with_error_details",
        ),
    ],
)
async def test_setup_retry_when_no_component_answers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    failed: dict[str, ModbusTimeoutError],
) -> None:
    """Test setup retries when no component returns an update."""
    unit = mock_connection.for_unit(DEFAULT_UNIT_ID)
    detection = await diematic_modbus.async_detect(unit)
    assert detection.device is not None
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.de_dietrich.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
                unit_id
            ),
        ),
        patch(
            "homeassistant.components.de_dietrich.diematic_modbus.async_detect",
            return_value=detection,
        ),
        patch.object(
            type(detection.device),
            "async_update",
            return_value=UpdateReport(
                updated=frozenset(),
                failed=failed,
            ),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_error_when_device_is_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup reports an unsupported device with detection evidence."""
    seed_boiler(mock_connection.for_unit(DEFAULT_UNIT_ID), boiler_type=999)
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert "This device is not supported" in mock_config_entry.reason
    assert "raw_type_code=999" in caplog.text


async def test_setup_isystem_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test setup registers iSystem software information."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "100"


async def test_setup_error_when_link_settings_conflict(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup reports incompatible shared Modbus link settings."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=HomeAssistantError("different framing"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        mock_config_entry.reason
        == "The boiler cannot be set up with these link settings: different framing"
    )


async def test_base_layout_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test base-layout device information omits unavailable metadata."""
    seed_boiler(mock_connection.for_unit(DEFAULT_UNIT_ID))
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        data=MOCK_USER_INPUT,
        title=MOCK_TITLE,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert device is not None
    assert device.name == "De Dietrich"
    assert device.manufacturer == "De Dietrich"
    assert device.model is None
    assert device.serial_number is None
    assert device.sw_version is None


@pytest.mark.parametrize(
    ("seed_fn", "expected_children"),
    [
        pytest.param(
            seed_isystem_boiler,
            {
                "circuit_a": ("Heating circuit A", "circuit_a_room_temperature"),
                "circuit_b": ("Heating circuit B", "circuit_b_room_temperature"),
                "circuit_c": ("Heating circuit C", "circuit_c_room_temperature"),
            },
            id="isystem",
        ),
        pytest.param(
            seed_boiler,
            {
                "circuit_a": ("Heating circuit A", "circuit_a_room_temperature"),
                "circuit_b": ("Heating circuit B", "circuit_b_room_temperature"),
            },
            id="base_layout",
        ),
    ],
)
async def test_child_devices_route_per_component_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    seed_fn: Callable[[MockModbusUnit], None],
    expected_children: dict[str, tuple[str, str]],
) -> None:
    """Test each present bundle has a child device and its sensors route to it."""
    seed_fn(mock_connection.for_unit(DEFAULT_UNIT_ID))
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    parent = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert parent is not None

    for bundle, (expected_name, sensor_key) in expected_children.items():
        child = device_registry.async_get_child_device_by_identifier(
            (DOMAIN, f"{mock_config_entry.entry_id}_{bundle}"),
            mock_config_entry.entry_id,
        )
        assert child is not None, f"Missing child device for {bundle}"
        assert child.name == expected_name

        entity_id = entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"{mock_config_entry.entry_id}_{sensor_key}"
        )
        assert entity_id is not None, f"Missing sensor for {bundle}"
        sensor_entry = entity_registry.async_get(entity_id)
        assert sensor_entry is not None
        assert sensor_entry.device_id == child.id

    outdoor_entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{mock_config_entry.entry_id}_outdoor_temperature"
    )
    assert outdoor_entity_id is not None
    outdoor_entry = entity_registry.async_get(outdoor_entity_id)
    assert outdoor_entry is not None
    assert outdoor_entry.device_id == parent.id


@pytest.mark.parametrize(
    ("seed_fn", "zapped_registers", "missing_bundle", "missing_sensor_key"),
    [
        pytest.param(
            seed_isystem_boiler,
            [614, 615, 621],
            "circuit_a",
            "circuit_a_room_temperature",
            id="isystem_no_circuit_a",
        ),
        pytest.param(
            seed_isystem_boiler,
            [616, 617, 605, 662, 663],
            "circuit_b",
            "circuit_b_room_temperature",
            id="isystem_no_circuit_b",
        ),
        pytest.param(
            seed_isystem_boiler,
            [618, 619],
            "circuit_c",
            "circuit_c_room_temperature",
            id="isystem_no_circuit_c",
        ),
        pytest.param(
            seed_boiler,
            [18, 21],
            "circuit_a",
            "circuit_a_room_temperature",
            id="base_no_circuit_a",
        ),
        pytest.param(
            seed_boiler,
            [27, 32, 33, 30, 31],
            "circuit_b",
            "circuit_b_room_temperature",
            id="base_no_circuit_b",
        ),
    ],
)
async def test_absent_bundle_has_no_child_device_or_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    seed_fn: Callable[[MockModbusUnit], None],
    zapped_registers: list[int],
    missing_bundle: str,
    missing_sensor_key: str,
) -> None:
    """Test a bundle with no live readings produces no child device and no per-component sensor."""
    unit = mock_connection.for_unit(DEFAULT_UNIT_ID)
    seed_fn(unit)
    for register in zapped_registers:
        unit.holding[register] = 0xFFFF
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_{missing_bundle}"),
        mock_config_entry.entry_id,
    )
    assert child is None, f"Absent bundle {missing_bundle} should have no child device"

    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{mock_config_entry.entry_id}_{missing_sensor_key}"
    )
    assert entity_id is None, (
        f"Absent bundle {missing_bundle} should have no {missing_sensor_key} entity"
    )


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test unloading the config entry unloads the sensor platform."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED
