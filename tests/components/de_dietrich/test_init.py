"""Test the De Dietrich setup."""

from unittest.mock import patch

import diematic_modbus
from diematic_modbus import UpdateReport
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.de_dietrich.const import DEFAULT_UNIT_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import MOCK_ENTRY_ID, MOCK_TITLE, MOCK_USER_INPUT, seed_boiler

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


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test unloading the config entry unloads the sensor platform."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED
