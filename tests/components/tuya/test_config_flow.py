"""Tests for the Tuya config flow."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import Manager

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.tuya.config_flow import (
    _INPUT_ENTRY_CLEAR_DEVICE_OPTIONS,
    _INPUT_ENTRY_DEVICE_SELECTION,
)
from homeassistant.components.tuya.const import CONF_USER_CODE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture
async def filled_device_registry(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> dr.DeviceRegistry:
    """Fill device registry with mock devices."""
    await initialize_entry(hass, mock_manager, mock_config_entry, [])
    for specs in (
        (
            "jzpap0inhkykqtlwgklc",
            "wltqkykhni0papzj",
            "Roller shutter Living Room",
            "tuya.jzpap0inhkykqtlwgklccontrol",
        ),
        (
            "2w46jyhngklc",
            "nhyj64w2",
            "Tapparelle studio",
            "tuya.2w46jyhngklccontrol",
        ),
    ):
        device_entry = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={(DOMAIN, specs[0])},
            manufacturer="Tuya",
            model_id=specs[1],
            name=specs[2],
        )
        entity_registry.async_get_or_create(
            config_entry=mock_config_entry,
            domain=COVER_DOMAIN,
            platform=DOMAIN,
            device_id=device_entry.id,
            unique_id=specs[3],
        )
    return device_registry


@pytest.mark.usefixtures("mock_tuya_login_control")
async def test_user_flow(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
    assert result3 == snapshot


async def test_user_flow_failed_qr_code(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
) -> None:
    """Test an error occurring while retrieving the QR code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Something went wrong getting the QR code (like an invalid user code)
    mock_tuya_login_control.qr_code.return_value["success"] = False

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("errors") == {"base": "login_error"}

    # This time it worked out
    mock_tuya_login_control.qr_code.return_value["success"] = True

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )
    assert result3.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.CREATE_ENTRY


async def test_user_flow_failed_scan(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
) -> None:
    """Test an error occurring while verifying login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "scan"

    # Access has been denied, or the code hasn't been scanned yet
    good_values = mock_tuya_login_control.login_result.return_value
    mock_tuya_login_control.login_result.return_value = (
        False,
        {"msg": "oops", "code": 42},
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.FORM
    assert result3.get("errors") == {"base": "login_error"}

    # This time it worked out
    mock_tuya_login_control.login_result.return_value = good_values

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result4.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_tuya_login_control")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the reauthentication configuration flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "scan"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"

    assert mock_config_entry == snapshot


async def test_reauth_flow_failed_qr_code(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an error occurring while retrieving the QR code."""
    mock_config_entry.add_to_hass(hass)

    # Something went wrong getting the QR code (like an invalid user code)
    mock_tuya_login_control.qr_code.return_value["success"] = False

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_user_code"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("errors") == {"base": "login_error"}

    # This time it worked out
    mock_tuya_login_control.qr_code.return_value["success"] = True

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )
    assert result3.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"


@pytest.mark.usefixtures("filled_device_registry")
async def test_user_options_clear(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test clearing the options."""
    # Verify that first config step comes back with a selection list of
    # all configurable devices
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"].schema["device_selection"].options == {
        "Roller shutter Living Room": False,
        "Tapparelle studio": False,
    }

    # Verify that the clear-input action clears the options dict
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={_INPUT_ENTRY_CLEAR_DEVICE_OPTIONS: True},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}


@pytest.mark.usefixtures("filled_device_registry")
async def test_user_options_empty_selection_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test leaving the selection of devices empty."""
    # Verify that first config step comes back with a selection list of
    # all configurable devices
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"].schema["device_selection"].options == {
        "Roller shutter Living Room": False,
        "Tapparelle studio": False,
    }

    # Verify that an empty selection shows the form again
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={_INPUT_ENTRY_DEVICE_SELECTION: []},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_selection"
    assert result["errors"] == {"base": "device_not_selected"}

    # Verify that a single selected device to configure comes back as a form with the device to configure
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={_INPUT_ENTRY_DEVICE_SELECTION: ["Roller shutter Living Room"]},
    )
    assert result["type"] is FlowResultType.FORM
    assert (
        result["description_placeholders"]["device_id"] == "Roller shutter Living Room"
    )

    # Verify that the setting for the device comes back as default when no input is given
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"]["device_options"]["jzpap0inhkykqtlwgklc"][
            "cover_position_reversed"
        ]
        is False
    )


@pytest.mark.usefixtures("filled_device_registry")
async def test_user_options_set_single(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuring a single device."""
    # Verify that first config step comes back with a selection list of
    # all configurable devices
    # Clear config options to certify functionality when starting from scratch
    object.__setattr__(mock_config_entry, "options", {})
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"].schema["device_selection"].options == {
        "Roller shutter Living Room": False,
        "Tapparelle studio": False,
    }

    # Verify that a single selected device to configure comes back as a form with the device to configure
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={_INPUT_ENTRY_DEVICE_SELECTION: ["Roller shutter Living Room"]},
    )
    assert result["type"] is FlowResultType.FORM
    assert (
        result["description_placeholders"]["device_id"] == "Roller shutter Living Room"
    )

    # Verify that the setting for the device comes back as default when no input is given
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"]["device_options"]["jzpap0inhkykqtlwgklc"][
            "cover_position_reversed"
        ]
        is False
    )


@pytest.mark.usefixtures("filled_device_registry")
async def test_user_options_set_multiple(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test configuring multiple consecutive devices in a row."""
    # Verify that first config step comes back with a selection list of
    # all configurable devices
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    for entry in dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    ):
        device_registry.async_update_device(entry.id, name_by_user="Given Name")
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["data_schema"].schema["device_selection"].options == {
        "Given Name (Roller shutter Living Room)": False,
        "Given Name (Tapparelle studio)": False,
    }

    # Verify that selecting two devices to configure comes back as a
    #  form with the first device to configure using it's long name as entry
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            _INPUT_ENTRY_DEVICE_SELECTION: [
                "Given Name (Roller shutter Living Room)",
                "Given Name (Tapparelle studio)",
            ]
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert (
        result["description_placeholders"]["device_id"]
        == "Given Name (Tapparelle studio)"
    )

    # Verify that next device is coming up for configuration after the first
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"cover_position_reversed": True},
    )
    assert result["type"] is FlowResultType.FORM
    assert (
        result["description_placeholders"]["device_id"]
        == "Given Name (Roller shutter Living Room)"
    )

    # Verify that the setting for the device comes back as default when no input is given
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"cover_position_reversed": False},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"]["device_options"]["jzpap0inhkykqtlwgklc"][
            "cover_position_reversed"
        ]
        is False
    )
    assert (
        result["data"]["device_options"]["2w46jyhngklc"]["cover_position_reversed"]
        is True
    )


async def test_user_options_no_devices(
    hass: HomeAssistant, mock_manager: Manager, mock_config_entry: MockConfigEntry
) -> None:
    """Test that options does not change when no devices are available."""
    await initialize_entry(hass, mock_manager, mock_config_entry, [])
    await hass.async_block_till_done()
    # Verify that first config step comes back with an empty list of possible devices to choose from
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_configurable_devices"
