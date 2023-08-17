"""Test the Home Assistant Yellow config flow."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.homeassistant_yellow.const import DOMAIN
from homeassistant.components.zha.core.const import DOMAIN as ZHA_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, MockModule, mock_integration


@pytest.fixture(name="get_yellow_settings")
def mock_get_yellow_settings():
    """Mock getting yellow settings."""
    with patch(
        "homeassistant.components.homeassistant_yellow.config_flow.async_get_yellow_settings",
        return_value={"disk_led": True, "heartbeat_led": True, "power_led": True},
    ) as get_yellow_settings:
        yield get_yellow_settings


@pytest.fixture(name="set_yellow_settings")
def mock_set_yellow_settings():
    """Mock setting yellow settings."""
    with patch(
        "homeassistant.components.homeassistant_yellow.config_flow.async_set_yellow_settings",
    ) as set_yellow_settings:
        yield set_yellow_settings


@pytest.fixture(name="reboot_host")
def mock_reboot_host():
    """Mock rebooting host."""
    with patch(
        "homeassistant.components.homeassistant_yellow.config_flow.async_reboot_host",
    ) as reboot_host:
        yield reboot_host


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""
    mock_integration(hass, MockModule("hassio"))

    with patch(
        "homeassistant.components.homeassistant_yellow.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant Yellow"
    assert result["data"] == {}
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {}
    assert config_entry.title == "Home Assistant Yellow"


async def test_config_flow_single_entry(hass: HomeAssistant) -> None:
    """Test only a single entry is allowed."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_yellow.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    mock_setup_entry.assert_not_called()


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
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"next_step_id": "multipan_settings"},
        )
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
                "device": "/dev/ttyAMA1",
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
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    zha_config_entry = MockConfigEntry(
        data={"device": {"path": "/dev/ttyAMA1"}, "radio_type": "ezsp"},
        domain=ZHA_DOMAIN,
        options={},
        title="Yellow",
    )
    zha_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"next_step_id": "multipan_settings"},
        )
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
                "device": "/dev/ttyAMA1",
                "baudrate": "115200",
                "flow_control": True,
            }
        },
    )
    # Check the ZHA config entry data is updated
    assert zha_config_entry.data == {
        "device": {
            "path": "socket://core-silabs-multiprotocol:9999",
            "baudrate": 57600,  # ZHA default
            "flow_control": "software",  # ZHA default
        },
        "radio_type": "ezsp",
    }

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "finish_addon_setup"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("reboot_menu_choice", "reboot_calls"),
    [("reboot_now", 1), ("reboot_later", 0)],
)
async def test_option_flow_led_settings(
    hass: HomeAssistant,
    get_yellow_settings,
    set_yellow_settings,
    reboot_host,
    reboot_menu_choice,
    reboot_calls,
) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "main_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "hardware_settings"},
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"disk_led": False, "heartbeat_led": False, "power_led": False},
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "reboot_menu"
    set_yellow_settings.assert_called_once_with(
        hass, {"disk_led": False, "heartbeat_led": False, "power_led": False}
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": reboot_menu_choice},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert len(reboot_host.mock_calls) == reboot_calls


async def test_option_flow_led_settings_unchanged(
    hass: HomeAssistant,
    get_yellow_settings,
    set_yellow_settings,
) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "main_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "hardware_settings"},
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"disk_led": True, "heartbeat_led": True, "power_led": True},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    set_yellow_settings.assert_not_called()


async def test_option_flow_led_settings_fail_1(hass: HomeAssistant) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "main_menu"

    with patch(
        "homeassistant.components.homeassistant_yellow.config_flow.async_get_yellow_settings",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"next_step_id": "hardware_settings"},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "read_hw_settings_error"


async def test_option_flow_led_settings_fail_2(
    hass: HomeAssistant, get_yellow_settings
) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "main_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "hardware_settings"},
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.homeassistant_yellow.config_flow.async_set_yellow_settings",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"disk_led": False, "heartbeat_led": False, "power_led": False},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "write_hw_settings_error"
