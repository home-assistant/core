"""Tests for 1-Wire config flow."""
from unittest.mock import MagicMock, patch

from homeassistant.components.onewire.const import (
    INPUT_ENTRY_CLEAR_OPTIONS,
    INPUT_ENTRY_DEVICE_SELECTION,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_owproxy_mock_devices
from .const import MOCK_OWPROXY_DEVICES


class FakeDevice:
    """Mock Class for mocking DeviceEntry."""

    name_by_user = "Given Name"


async def test_user_options_clear(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    owproxy: MagicMock,
):
    """Test clearing the options."""
    setup_owproxy_mock_devices(
        owproxy, Platform.SENSOR, [x for x in MOCK_OWPROXY_DEVICES if "28." in x]
    )

    # Verify that first config step comes back with a selection list of all the 28-family devices
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["data_schema"].schema["device_selection"].options == {
        "28.111111111111": False,
        "28.222222222222": False,
        "28.222222222223": False,
    }

    # Verify that the clear-input action clears the options dict
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={INPUT_ENTRY_CLEAR_OPTIONS: True},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {}


async def test_user_options_empty_selection(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    owproxy: MagicMock,
):
    """Test leaving the selection of devices empty."""
    setup_owproxy_mock_devices(
        owproxy, Platform.SENSOR, [x for x in MOCK_OWPROXY_DEVICES if "28." in x]
    )

    # Verify that first config step comes back with a selection list of all the 28-family devices
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["data_schema"].schema["device_selection"].options == {
        "28.111111111111": False,
        "28.222222222222": False,
        "28.222222222223": False,
    }

    # Verify that an empty selection does not modify the options
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={INPUT_ENTRY_DEVICE_SELECTION: []},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "device_selection"
    assert result["errors"] == {"base": "device_not_selected"}


async def test_user_options_set_single(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    owproxy: MagicMock,
):
    """Test configuring a single device."""
    setup_owproxy_mock_devices(
        owproxy, Platform.SENSOR, [x for x in MOCK_OWPROXY_DEVICES if "28." in x]
    )

    # Clear config options to certify functionality when starting from scratch
    config_entry.options = {}

    # Verify that first config step comes back with a selection list of all the 28-family devices
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["data_schema"].schema["device_selection"].options == {
        "28.111111111111": False,
        "28.222222222222": False,
        "28.222222222223": False,
    }

    # Verify that a single selected device to configure comes back as a form with the device to configure
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={INPUT_ENTRY_DEVICE_SELECTION: ["28.111111111111"]},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["description_placeholders"]["sensor_id"] == "28.111111111111"

    # Verify that the setting for the device comes back as default when no input is given
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result["data"]["device_options"]["28.111111111111"]["precision"]
        == "temperature"
    )


async def test_user_options_set_multiple(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    owproxy: MagicMock,
):
    """Test configuring multiple consecutive devices in a row."""
    setup_owproxy_mock_devices(
        owproxy, Platform.SENSOR, [x for x in MOCK_OWPROXY_DEVICES if "28." in x]
    )

    # Initialize onewire hub
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify that first config step comes back with a selection list of all the 28-family devices
    with patch(
        "homeassistant.helpers.device_registry.DeviceRegistry.async_get_device",
        return_value=FakeDevice(),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["data_schema"].schema["device_selection"].options == {
        "Given Name (28.111111111111)": False,
        "Given Name (28.222222222222)": False,
        "Given Name (28.222222222223)": False,
    }

    # Verify that selecting two devices to configure comes back as a
    #  form with the first device to configure using it's long name as entry
    with patch(
        "homeassistant.helpers.device_registry.DeviceRegistry.async_get_device",
        return_value=FakeDevice(),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                INPUT_ENTRY_DEVICE_SELECTION: [
                    "Given Name (28.111111111111)",
                    "Given Name (28.222222222222)",
                ]
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert (
        result["description_placeholders"]["sensor_id"]
        == "Given Name (28.222222222222)"
    )

    # Verify that next sensor is coming up for configuration after the first
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"precision": "temperature"},
    )
    assert result["type"] == FlowResultType.FORM
    assert (
        result["description_placeholders"]["sensor_id"]
        == "Given Name (28.111111111111)"
    )

    # Verify that the setting for the device comes back as default when no input is given
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"precision": "temperature9"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result["data"]["device_options"]["28.222222222222"]["precision"]
        == "temperature"
    )
    assert (
        result["data"]["device_options"]["28.111111111111"]["precision"]
        == "temperature9"
    )


async def test_user_options_no_devices(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    owproxy: MagicMock,
):
    """Test that options does not change when no devices are available."""
    # Initialize onewire hub
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify that first config step comes back with an empty list of possible devices to choose from
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "No configurable devices found."
