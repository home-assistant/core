"""Test the Home Assistant Yellow config flow."""
from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.homeassistant_hardware import silabs_multiprotocol_addon
from homeassistant.components.zha.core.const import DOMAIN as ZHA_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from tests.common import MockConfigEntry, MockModule, mock_integration, mock_platform

TEST_DOMAIN = "test"


class TestConfigFlow(ConfigFlow, domain=TEST_DOMAIN):
    """Handle a config flow for Home Assistant Yellow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TestOptionsFlow:
        """Return the options flow."""
        return TestOptionsFlow(config_entry)

    async def async_step_system(self, data: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Home Assistant Yellow", data={})


class TestOptionsFlow(silabs_multiprotocol_addon.OptionsFlowHandler):
    """Handle an option flow for Home Assistant Yellow."""

    async def _async_serial_port_settings(
        self,
    ) -> silabs_multiprotocol_addon.SerialPortSettings:
        """Return the radio serial port settings."""
        return silabs_multiprotocol_addon.SerialPortSettings(
            device="/dev/ttyTEST123",
            baudrate="115200",
            flow_control=True,
        )

    def _zha_name(self) -> str:
        """Return the ZHA name."""
        return "Test Multi-PAN"


@pytest.fixture(autouse=True)
def config_flow_handler(
    hass: HomeAssistant, current_request_with_host: Any
) -> Generator[TestConfigFlow, None, None]:
    """Fixture for a test config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestConfigFlow}):
        yield TestConfigFlow


async def test_option_flow_install_multi_pan_addon(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": True,
        },
    )
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"
    assert result["progress_action"] == "install_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "configure_addon"
    install_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    addon_info.return_value["hostname"] = "blah"
    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    set_addon_options.assert_called_once_with(
        hass,
        "core_silabs_multiprotocol",
        {
            "options": {
                "autoflash_firmware": True,
                "device": "/dev/ttyTEST123",
                "baudrate": "115200",
                "flow_control": True,
            }
        },
    )

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "finish_addon_setup"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_option_flow_install_multi_pan_addon_zha(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
) -> None:
    """Test installing the multi pan addon when a zha config entry exists."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    zha_config_entry = MockConfigEntry(
        data={"device": {"path": "/dev/ttyTEST123"}, "radio_type": "ezsp"},
        domain=ZHA_DOMAIN,
        options={},
        title="Test",
    )
    zha_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": True,
        },
    )
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"
    assert result["progress_action"] == "install_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "configure_addon"
    install_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    set_addon_options.assert_called_once_with(
        hass,
        "core_silabs_multiprotocol",
        {
            "options": {
                "autoflash_firmware": True,
                "device": "/dev/ttyTEST123",
                "baudrate": "115200",
                "flow_control": True,
            }
        },
    )
    # Check the ZHA migration flow has been started and config entry data is updated
    assert hass.config_entries.options.async_has_matching_flow(
        zha_config_entry.entry_id,
        {"source": "yellow_migration"},
        {
            "name": "Test Multi-PAN",
            "new_port": {
                "path": "socket://core-silabs-multiprotocol:9999",
                "baudrate": 115200,
                "flow_control": "hardware",
            },
            "new_radio_type": "efr32",
            "old_port": {
                "path": "/dev/ttyTEST123",
                "baudrate": 115200,
                "flow_control": "hardware",
            },
            "old_radio_type": "efr32",
        },
    )
    zha_option_flows = hass.config_entries.options.async_progress_by_handler(
        zha_config_entry.entry_id
    )
    assert len(zha_option_flows) == 1
    assert zha_option_flows[0]["step_id"] == "finish_yellow_migration"
    assert zha_config_entry.data == {
        "device": {
            "path": "socket://core-silabs-multiprotocol:9999",
            "baudrate": 115200,
            "flow_control": "hardware",
        },
        "radio_type": "ezsp",
    }
    assert zha_config_entry.title == "Test Multi-PAN"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "finish_addon_setup"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    # Check the ZHA migration flow is not yet finished
    zha_option_flows = hass.config_entries.options.async_progress_by_handler(
        zha_config_entry.entry_id
    )
    assert len(zha_option_flows) == 1
    assert zha_option_flows[0]["step_id"] == "finish_yellow_migration"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Check the ZHA migration flow is finished
    zha_option_flows = hass.config_entries.options.async_progress_by_handler(
        zha_config_entry.entry_id
    )
    assert len(zha_option_flows) == 0


async def test_option_flow_install_multi_pan_addon_zha_other_radio(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
) -> None:
    """Test installing the multi pan addon when a zha config entry exists."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    zha_config_entry = MockConfigEntry(
        data={
            "device": {
                "path": "/dev/other_radio",
                "baudrate": 115200,
                "flow_control": "hardware",
            },
            "radio_type": "ezsp",
        },
        domain=ZHA_DOMAIN,
        options={},
        title="Yellow",
    )
    zha_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": True,
        },
    )
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"
    assert result["progress_action"] == "install_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "configure_addon"
    install_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    addon_info.return_value["hostname"] = "core-silabs-multiprotocol"
    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    set_addon_options.assert_called_once_with(
        hass,
        "core_silabs_multiprotocol",
        {
            "options": {
                "autoflash_firmware": True,
                "device": "/dev/ttyTEST123",
                "baudrate": "115200",
                "flow_control": True,
            }
        },
    )
    # Check the ZHA migration has already finished
    zha_option_flows = hass.config_entries.options.async_progress_by_handler(
        zha_config_entry.entry_id
    )
    assert len(zha_option_flows) == 0

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "finish_addon_setup"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Check the ZHA entry data is not changed
    assert zha_config_entry.data == {
        "device": {
            "path": "/dev/other_radio",
            "baudrate": 115200,
            "flow_control": "hardware",
        },
        "radio_type": "ezsp",
    }


async def test_option_flow_non_hassio(
    hass: HomeAssistant,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_hassio"


async def test_option_flow_addon_installed_other_device(
    hass: HomeAssistant,
    addon_store_info,
    addon_installed,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_installed_other_device"

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_option_flow_addon_installed_same_device(
    hass: HomeAssistant,
    addon_info,
    addon_store_info,
    addon_installed,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))
    addon_info.return_value["options"]["device"] = "/dev/ttyTEST123"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "show_revert_guide"

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_option_flow_do_not_install_multi_pan_addon(
    hass: HomeAssistant,
    addon_info,
    addon_store_info,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": False,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
