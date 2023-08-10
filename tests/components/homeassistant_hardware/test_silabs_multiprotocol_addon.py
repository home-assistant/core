"""Test the Home Assistant Hardware silabs multiprotocol addon manager."""
from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.hassio import AddonError, AddonState
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.homeassistant_hardware import silabs_multiprotocol_addon
from homeassistant.components.zha.core.const import DOMAIN as ZHA_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.setup import ATTR_COMPONENT

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    flush_store,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"
TEST_DOMAIN_2 = "test_2"


class FakeConfigFlow(ConfigFlow):
    """Handle a config flow for the silabs multiprotocol add-on."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> FakeOptionsFlow:
        """Return the options flow."""
        return FakeOptionsFlow(config_entry)

    async def async_step_system(self, data: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Test HW", data={})


class FakeOptionsFlow(silabs_multiprotocol_addon.OptionsFlowHandler):
    """Handle an option flow for the silabs multiprotocol add-on."""

    async def _async_serial_port_settings(
        self,
    ) -> silabs_multiprotocol_addon.SerialPortSettings:
        """Return the radio serial port settings."""
        return silabs_multiprotocol_addon.SerialPortSettings(
            device="/dev/ttyTEST123",
            baudrate="115200",
            flow_control=True,
        )

    async def _async_zha_physical_discovery(self) -> dict[str, Any]:
        """Return ZHA discovery data when multiprotocol FW is not used.

        Passed to ZHA do determine if the ZHA config entry is connected to the radio
        being migrated.
        """
        return {
            "hw": {
                "name": "Test",
                "port": {
                    "path": "/dev/ttyTEST123",
                    "baudrate": 115200,
                    "flow_control": "hardware",
                },
                "radio_type": "efr32",
            }
        }

    def _zha_name(self) -> str:
        """Return the ZHA name."""
        return "Test Multi-PAN"

    def _hardware_name(self) -> str:
        """Return the name of the hardware."""
        return "Test"


@pytest.fixture(autouse=True)
def config_flow_handler(
    hass: HomeAssistant, current_request_with_host: Any
) -> Generator[FakeConfigFlow, None, None]:
    """Fixture for a test config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with mock_config_flow(TEST_DOMAIN, FakeConfigFlow):
        yield


@pytest.fixture
def options_flow_poll_addon_state():
    """Fixture for patching options flow addon state polling."""
    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.OptionsFlowHandler._async_wait_until_addon_state"
    ):
        yield


class MockMultiprotocolPlatform(MockPlatform):
    """A mock multiprotocol platform."""

    channel = 15
    using_multipan = True

    def __init__(self, **kwargs: Any) -> None:
        """Initialize."""
        super().__init__(**kwargs)
        self.change_channel_calls = []

    async def async_change_channel(
        self, hass: HomeAssistant, channel: int, delay: float
    ) -> None:
        """Set the channel to be used."""
        self.change_channel_calls.append((channel, delay))

    async def async_get_channel(self, hass: HomeAssistant) -> int | None:
        """Return the channel."""
        return self.channel

    async def async_using_multipan(self, hass: HomeAssistant) -> bool:
        """Return if the multiprotocol device is used."""
        return self.using_multipan


@pytest.fixture
def mock_multiprotocol_platform(
    hass: HomeAssistant,
) -> Generator[FakeConfigFlow, None, None]:
    """Fixture for a test silabs multiprotocol platform."""
    hass.config.components.add(TEST_DOMAIN)
    platform = MockMultiprotocolPlatform()
    mock_platform(hass, f"{TEST_DOMAIN}.silabs_multiprotocol", platform)
    return platform


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema:
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@patch(
    "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.ADDON_STATE_POLL_INTERVAL",
    0,
)
async def test_uninstall_addon(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    uninstall_addon,
):
    """Test the synchronous addon uninstall helper."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

    flow = hass.config_entries.options._progress[result["flow_id"]]
    multipan_manager = await silabs_multiprotocol_addon.get_addon_manager(hass)
    multipan_manager.async_get_addon_info = AsyncMock()
    multipan_manager.async_uninstall_addon = AsyncMock(
        wraps=multipan_manager.async_uninstall_addon
    )

    # First try uninstalling the addon when it is already uninstalled
    multipan_manager.async_get_addon_info.side_effect = [
        Mock(state=AddonState.NOT_INSTALLED)
    ]
    await flow._async_uninstall_addon(multipan_manager)
    multipan_manager.async_uninstall_addon.assert_not_called()

    # Next, try uninstalling the addon but in a complex case where the API fails first
    multipan_manager.async_get_addon_info.side_effect = [
        # First the API fails
        AddonError(),
        AddonError(),
        # Then the addon is still running
        Mock(state=AddonState.RUNNING),
        # And finally it is uninstalled
        Mock(state=AddonState.NOT_INSTALLED),
    ]
    await flow._async_uninstall_addon(multipan_manager)
    multipan_manager.async_uninstall_addon.assert_called_once()


async def test_option_flow_install_multi_pan_addon(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
    options_flow_poll_addon_state,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
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
    options_flow_poll_addon_state,
) -> None:
    """Test installing the multi pan addon when a zha config entry exists."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
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

    multipan_manager = await silabs_multiprotocol_addon.get_addon_manager(hass)
    assert multipan_manager._channel is None
    with patch(
        "homeassistant.components.zha.silabs_multiprotocol.async_get_channel",
        return_value=11,
    ):
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
    # Check the channel is initialized from ZHA
    assert multipan_manager._channel == 11
    # Check the ZHA config entry data is updated
    assert zha_config_entry.data == {
        "device": {
            "path": "socket://core-silabs-multiprotocol:9999",
            "baudrate": 57600,  # ZHA default
            "flow_control": "software",  # ZHA default
        },
        "radio_type": "ezsp",
    }
    assert zha_config_entry.title == "Test Multi-PAN"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "finish_addon_setup"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_option_flow_install_multi_pan_addon_zha_other_radio(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
    options_flow_poll_addon_state,
) -> None:
    """Test installing the multi pan addon when a zha config entry exists."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
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
        title="Test HW",
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
    """Test installing the multi pan addon on a Core installation, without hassio."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
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
        title="Test HW",
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


@pytest.mark.parametrize(
    ("configured_channel", "suggested_channel"), [(None, "15"), (11, "11")]
)
async def test_option_flow_addon_installed_same_device_reconfigure_unexpected_users(
    hass: HomeAssistant,
    addon_info,
    addon_store_info,
    addon_installed,
    mock_multiprotocol_platform: MockMultiprotocolPlatform,
    configured_channel: int | None,
    suggested_channel: int,
) -> None:
    """Test reconfiguring the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))
    addon_info.return_value["options"]["device"] = "/dev/ttyTEST123"

    multipan_manager = await silabs_multiprotocol_addon.get_addon_manager(hass)
    multipan_manager._channel = configured_channel

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "addon_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "reconfigure_addon"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "notify_unknown_multipan_user"

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "change_channel"
    assert get_suggested(result["data_schema"].schema, "channel") == suggested_channel

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"channel": "14"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "notify_channel_change"
    assert result["description_placeholders"] == {"delay_minutes": "5"}

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY

    assert mock_multiprotocol_platform.change_channel_calls == [(14, 300)]
    assert multipan_manager._channel == 14


@pytest.mark.parametrize(
    ("configured_channel", "suggested_channel"), [(None, "15"), (11, "11")]
)
async def test_option_flow_addon_installed_same_device_reconfigure_expected_users(
    hass: HomeAssistant,
    addon_info,
    addon_store_info,
    addon_installed,
    configured_channel: int | None,
    suggested_channel: int,
) -> None:
    """Test reconfiguring the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))
    addon_info.return_value["options"]["device"] = "/dev/ttyTEST123"

    multipan_manager = await silabs_multiprotocol_addon.get_addon_manager(hass)
    multipan_manager._channel = configured_channel

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
    )
    config_entry.add_to_hass(hass)

    mock_multiprotocol_platforms = {}
    for domain in ["otbr", "zha"]:
        mock_multiprotocol_platform = MockMultiprotocolPlatform()
        mock_multiprotocol_platforms[domain] = mock_multiprotocol_platform
        mock_multiprotocol_platform.channel = configured_channel
        mock_multiprotocol_platform.using_multipan = True

        hass.config.components.add(domain)
        mock_platform(
            hass, f"{domain}.silabs_multiprotocol", mock_multiprotocol_platform
        )
        hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: domain})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "addon_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "reconfigure_addon"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "change_channel"
    assert get_suggested(result["data_schema"].schema, "channel") == suggested_channel

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"channel": "14"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "notify_channel_change"
    assert result["description_placeholders"] == {"delay_minutes": "5"}

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY

    for domain in ["otbr", "zha"]:
        assert mock_multiprotocol_platforms[domain].change_channel_calls == [(14, 300)]
    assert multipan_manager._channel == 14


async def test_option_flow_addon_installed_same_device_uninstall(
    hass: HomeAssistant,
    addon_info,
    addon_store_info,
    addon_installed,
    install_addon,
    start_addon,
    stop_addon,
    uninstall_addon,
    set_addon_options,
    options_flow_poll_addon_state,
) -> None:
    """Test uninstalling the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))
    addon_info.return_value["options"]["device"] = "/dev/ttyTEST123"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
    )
    config_entry.add_to_hass(hass)

    zha_config_entry = MockConfigEntry(
        data={
            "device": {"path": "socket://core-silabs-multiprotocol:9999"},
            "radio_type": "ezsp",
        },
        domain=ZHA_DOMAIN,
        options={},
        title="Test Multi-PAN",
    )
    zha_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "addon_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "uninstall_addon"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "uninstall_addon"

    # Make sure the flasher addon is installed
    addon_store_info.return_value = {
        "installed": None,
        "available": True,
        "state": "not_installed",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {silabs_multiprotocol_addon.CONF_DISABLE_MULTI_PAN: True}
    )

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_flasher_addon"
    assert result["progress_action"] == "install_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "configure_flasher_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "uninstall_multiprotocol_addon"
    assert result["progress_action"] == "uninstall_multiprotocol_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    uninstall_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "start_flasher_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_flasher_addon"
    assert result["progress_action"] == "start_flasher_addon"
    assert result["description_placeholders"] == {"addon_name": "Silicon Labs Flasher"}

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    install_addon.assert_called_once_with(hass, "core_silabs_flasher")
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "flashing_complete"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Check the ZHA config entry data is updated
    assert zha_config_entry.data == {
        "device": {
            "path": "/dev/ttyTEST123",
            "baudrate": 115200,
            "flow_control": "hardware",
        },
        "radio_type": "ezsp",
    }
    assert zha_config_entry.title == "Test"


async def test_option_flow_addon_installed_same_device_do_not_uninstall_multi_pan(
    hass: HomeAssistant,
    addon_info,
    addon_store_info,
    addon_installed,
    install_addon,
    start_addon,
    stop_addon,
    uninstall_addon,
    set_addon_options,
) -> None:
    """Test uninstalling the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))
    addon_info.return_value["options"]["device"] = "/dev/ttyTEST123"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "addon_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "uninstall_addon"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "uninstall_addon"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {silabs_multiprotocol_addon.CONF_DISABLE_MULTI_PAN: False}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_option_flow_flasher_already_running_failure(
    hass: HomeAssistant,
    addon_info,
    addon_store_info,
    addon_installed,
    install_addon,
    start_addon,
    stop_addon,
    uninstall_addon,
    set_addon_options,
    options_flow_poll_addon_state,
) -> None:
    """Test uninstalling the multi pan addon but with the flasher addon running."""
    mock_integration(hass, MockModule("hassio"))
    addon_info.return_value["options"]["device"] = "/dev/ttyTEST123"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "addon_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "uninstall_addon"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "uninstall_addon"

    # The flasher addon is already installed and running, this is bad
    addon_store_info.return_value["installed"] = True
    addon_info.return_value["state"] = "started"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {silabs_multiprotocol_addon.CONF_DISABLE_MULTI_PAN: True}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_install_failed"


async def test_option_flow_addon_installed_same_device_flasher_already_installed(
    hass: HomeAssistant,
    addon_info,
    addon_store_info,
    addon_installed,
    install_addon,
    start_addon,
    stop_addon,
    uninstall_addon,
    set_addon_options,
    options_flow_poll_addon_state,
) -> None:
    """Test uninstalling the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))
    addon_info.return_value["options"]["device"] = "/dev/ttyTEST123"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "addon_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "uninstall_addon"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "uninstall_addon"

    addon_store_info.return_value = {
        "installed": True,
        "available": True,
        "state": "not_running",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {silabs_multiprotocol_addon.CONF_DISABLE_MULTI_PAN: True}
    )
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "uninstall_multiprotocol_addon"
    assert result["progress_action"] == "uninstall_multiprotocol_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    uninstall_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "start_flasher_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_flasher_addon"
    assert result["progress_action"] == "start_flasher_addon"
    assert result["description_placeholders"] == {"addon_name": "Silicon Labs Flasher"}

    addon_store_info.return_value = {
        "installed": True,
        "available": True,
        "state": "not_running",
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"])
    install_addon.assert_not_called()
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "flashing_complete"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_option_flow_flasher_install_failure(
    hass: HomeAssistant,
    addon_info,
    addon_store_info,
    addon_installed,
    install_addon,
    start_addon,
    stop_addon,
    uninstall_addon,
    set_addon_options,
    options_flow_poll_addon_state,
) -> None:
    """Test uninstalling the multi pan addon, case where flasher addon fails."""
    mock_integration(hass, MockModule("hassio"))
    addon_info.return_value["options"]["device"] = "/dev/ttyTEST123"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
    )
    config_entry.add_to_hass(hass)

    zha_config_entry = MockConfigEntry(
        data={
            "device": {"path": "socket://core-silabs-multiprotocol:9999"},
            "radio_type": "ezsp",
        },
        domain=ZHA_DOMAIN,
        options={},
        title="Test Multi-PAN",
    )
    zha_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "addon_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "uninstall_addon"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "uninstall_addon"

    addon_store_info.return_value = {
        "installed": None,
        "available": True,
        "state": "not_installed",
    }
    install_addon.side_effect = [AddonError()]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {silabs_multiprotocol_addon.CONF_DISABLE_MULTI_PAN: True}
    )

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_flasher_addon"
    assert result["progress_action"] == "install_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "install_failed"
    install_addon.assert_called_once_with(hass, "core_silabs_flasher")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_install_failed"


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
        title="Test HW",
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


async def test_option_flow_install_multi_pan_addon_install_fails(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))
    install_addon.side_effect = HassioAPIError("Boom")

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
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
    assert result["step_id"] == "install_failed"
    install_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_install_failed"


async def test_option_flow_install_multi_pan_addon_start_fails(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))
    start_addon.side_effect = HassioAPIError("Boom")

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
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
    assert result["step_id"] == "start_failed"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"


async def test_option_flow_install_multi_pan_addon_set_options_fails(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))
    set_addon_options.side_effect = HassioAPIError("Boom")

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
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

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_set_config_failed"


async def test_option_flow_addon_info_fails(
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))
    addon_store_info.side_effect = HassioAPIError("Boom")

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "addon_info_failed"


@patch(
    "homeassistant.components.zha.radio_manager.ZhaMultiPANMigrationHelper.async_initiate_migration",
    side_effect=Exception("Boom!"),
)
async def test_option_flow_install_multi_pan_addon_zha_migration_fails_step_1(
    mock_initiate_migration,
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
        title="Test HW",
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
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "zha_migration_failed"
    set_addon_options.assert_not_called()


@patch(
    "homeassistant.components.zha.radio_manager.ZhaMultiPANMigrationHelper.async_finish_migration",
    side_effect=Exception("Boom!"),
)
async def test_option_flow_install_multi_pan_addon_zha_migration_fails_step_2(
    mock_finish_migration,
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
    options_flow_poll_addon_state,
) -> None:
    """Test installing the multi pan addon."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=TEST_DOMAIN,
        options={},
        title="Test HW",
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

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "finish_addon_setup"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "zha_migration_failed"


def test_is_multiprotocol_url() -> None:
    """Test is_multiprotocol_url."""
    assert silabs_multiprotocol_addon.is_multiprotocol_url(
        "socket://core-silabs-multiprotocol:9999"
    )
    assert silabs_multiprotocol_addon.is_multiprotocol_url(
        "http://core-silabs-multiprotocol:8081"
    )
    assert not silabs_multiprotocol_addon.is_multiprotocol_url("/dev/ttyAMA1")


@pytest.mark.parametrize(
    (
        "initial_multipan_channel",
        "platform_using_multipan",
        "platform_channel",
        "new_multipan_channel",
    ),
    [
        (None, True, 15, 15),
        (None, False, 15, None),
        (11, True, 15, 11),
        (None, True, None, None),
    ],
)
async def test_import_channel(
    hass: HomeAssistant,
    initial_multipan_channel: int | None,
    platform_using_multipan: bool,
    platform_channel: int | None,
    new_multipan_channel: int | None,
) -> None:
    """Test channel is initialized from first platform."""
    multipan_manager = await silabs_multiprotocol_addon.get_addon_manager(hass)
    multipan_manager._channel = initial_multipan_channel

    mock_multiprotocol_platform = MockMultiprotocolPlatform()
    mock_multiprotocol_platform.channel = platform_channel
    mock_multiprotocol_platform.using_multipan = platform_using_multipan

    hass.config.components.add(TEST_DOMAIN)
    mock_platform(
        hass, f"{TEST_DOMAIN}.silabs_multiprotocol", mock_multiprotocol_platform
    )
    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: TEST_DOMAIN})
    await hass.async_block_till_done()

    assert multipan_manager.async_get_channel() == new_multipan_channel


@pytest.mark.parametrize(
    (
        "platform_using_multipan",
        "expected_calls",
    ),
    [
        (True, [(15, 10)]),
        (False, []),
    ],
)
async def test_change_channel(
    hass: HomeAssistant,
    mock_multiprotocol_platform: MockMultiprotocolPlatform,
    platform_using_multipan: bool,
    expected_calls: list[int],
) -> None:
    """Test channel is initialized from first platform."""
    multipan_manager = await silabs_multiprotocol_addon.get_addon_manager(hass)
    mock_multiprotocol_platform.using_multipan = platform_using_multipan

    await multipan_manager.async_change_channel(15, 10)
    assert mock_multiprotocol_platform.change_channel_calls == expected_calls


async def test_load_preferences(hass: HomeAssistant) -> None:
    """Make sure that we can load/save data correctly."""
    multipan_manager = await silabs_multiprotocol_addon.get_addon_manager(hass)
    assert multipan_manager._channel != 11
    multipan_manager.async_set_channel(11)

    await flush_store(multipan_manager._store)

    multipan_manager2 = silabs_multiprotocol_addon.MultiprotocolAddonManager(hass)
    await multipan_manager2.async_setup()

    assert multipan_manager._channel == multipan_manager2._channel


@pytest.mark.parametrize(
    (
        "multipan_platforms",
        "active_platforms",
    ),
    [
        ({}, []),
        ({TEST_DOMAIN: False}, []),
        ({TEST_DOMAIN: True}, [TEST_DOMAIN]),
        ({TEST_DOMAIN: True, TEST_DOMAIN_2: False}, [TEST_DOMAIN]),
        ({TEST_DOMAIN: True, TEST_DOMAIN_2: True}, [TEST_DOMAIN, TEST_DOMAIN_2]),
    ],
)
async def test_active_plaforms(
    hass: HomeAssistant,
    multipan_platforms: dict[str, bool],
    active_platforms: list[str],
) -> None:
    """Test async_active_platforms."""
    multipan_manager = await silabs_multiprotocol_addon.get_addon_manager(hass)

    for domain, platform_using_multipan in multipan_platforms.items():
        mock_multiprotocol_platform = MockMultiprotocolPlatform()
        mock_multiprotocol_platform.channel = 11
        mock_multiprotocol_platform.using_multipan = platform_using_multipan

        hass.config.components.add(domain)
        mock_platform(
            hass, f"{domain}.silabs_multiprotocol", mock_multiprotocol_platform
        )
        hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: domain})

    await hass.async_block_till_done()
    assert await multipan_manager.async_active_platforms() == active_platforms
