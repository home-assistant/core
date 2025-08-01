"""Test the Home Assistant Yellow config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.hassio import (
    DOMAIN as HASSIO_DOMAIN,
    AddonInfo,
    AddonState,
)
from homeassistant.components.homeassistant_hardware.firmware_config_flow import (
    STEP_PICK_FIRMWARE_THREAD,
    STEP_PICK_FIRMWARE_ZIGBEE,
)
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    CONF_DISABLE_MULTI_PAN,
    get_flasher_addon_manager,
    get_multiprotocol_addon_manager,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
)
from homeassistant.components.homeassistant_yellow.const import DOMAIN, RADIO_DEVICE
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration


@pytest.fixture(autouse=True)
def config_flow_handler(hass: HomeAssistant) -> Generator[None]:
    """Fixture for a test config flow."""
    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.WaitingAddonManager.async_wait_until_addon_state"
    ):
        yield


@pytest.fixture(autouse=True)
def mock_get_supervisor_client(supervisor_client: AsyncMock) -> Generator[None]:
    """Mock get_supervisor_client method."""
    with patch(
        "homeassistant.components.homeassistant_yellow.config_flow.get_supervisor_client",
        return_value=supervisor_client,
    ):
        yield


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
def mock_reboot_host(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock rebooting host."""
    return supervisor_client.host.reboot


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    with (
        patch(
            "homeassistant.components.homeassistant_yellow.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.probe_silabs_firmware_info",
            return_value=FirmwareInfo(
                device=RADIO_DEVICE,
                firmware_type=ApplicationType.EZSP,
                firmware_version=None,
                owners=[],
                source="probe",
            ),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant Yellow"
    assert result["data"] == {"firmware": "ezsp", "firmware_version": None}
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {"firmware": "ezsp", "firmware_version": None}
    assert config_entry.options == {}
    assert config_entry.title == "Home Assistant Yellow"


async def test_config_flow_single_entry(hass: HomeAssistant) -> None:
    """Test only a single entry is allowed."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.EZSP},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_yellow.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    mock_setup_entry.assert_not_called()


@pytest.mark.parametrize(
    ("reboot_menu_choice", "reboot_calls"),
    [("reboot_now", 1), ("reboot_later", 0)],
)
async def test_option_flow_led_settings(
    hass: HomeAssistant,
    get_yellow_settings: AsyncMock,
    set_yellow_settings: AsyncMock,
    reboot_host: AsyncMock,
    reboot_menu_choice: str,
    reboot_calls: int,
) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.EZSP},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "main_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "hardware_settings"},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"disk_led": False, "heartbeat_led": False, "power_led": False},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reboot_menu"
    set_yellow_settings.assert_called_once_with(
        hass, {"disk_led": False, "heartbeat_led": False, "power_led": False}
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": reboot_menu_choice},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert reboot_host.call_count == reboot_calls


async def test_option_flow_led_settings_unchanged(
    hass: HomeAssistant,
    get_yellow_settings,
    set_yellow_settings,
) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.EZSP},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "main_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "hardware_settings"},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"disk_led": True, "heartbeat_led": True, "power_led": True},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    set_yellow_settings.assert_not_called()


async def test_option_flow_led_settings_fail_1(hass: HomeAssistant) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.EZSP},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "main_menu"

    with patch(
        "homeassistant.components.homeassistant_yellow.config_flow.async_get_yellow_settings",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"next_step_id": "hardware_settings"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "read_hw_settings_error"


async def test_option_flow_led_settings_fail_2(
    hass: HomeAssistant, get_yellow_settings
) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.EZSP},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "main_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "hardware_settings"},
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.homeassistant_yellow.config_flow.async_set_yellow_settings",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"disk_led": False, "heartbeat_led": False, "power_led": False},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "write_hw_settings_error"


@pytest.mark.parametrize(
    ("step", "fw_type", "fw_version"),
    [
        (STEP_PICK_FIRMWARE_ZIGBEE, ApplicationType.EZSP, "7.4.4.0 build 0"),
        (STEP_PICK_FIRMWARE_THREAD, ApplicationType.SPINEL, "2.4.4.0"),
    ],
)
@pytest.mark.usefixtures("addon_store_info")
async def test_firmware_options_flow(
    step: str, fw_type: ApplicationType, fw_version: str, hass: HomeAssistant
) -> None:
    """Test the firmware options flow for Yellow."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.SPINEL},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    # First step is confirmation
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "main_menu"
    assert "firmware_settings" in result["menu_options"]

    # Pick firmware settings
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "firmware_settings"},
    )

    assert result["step_id"] == "pick_firmware"
    assert result["description_placeholders"]["firmware_type"] == "spinel"
    assert result["description_placeholders"]["model"] == "Home Assistant Yellow"

    async def mock_async_step_pick_firmware_zigbee(self, data):
        return await self.async_step_pre_confirm_zigbee()

    async def mock_install_firmware_step(
        self,
        fw_update_url: str,
        fw_type: str,
        firmware_name: str,
        expected_installed_firmware_type: ApplicationType,
        step_id: str,
        next_step_id: str,
    ) -> ConfigFlowResult:
        if next_step_id == "start_otbr_addon":
            next_step_id = "pre_confirm_otbr"

        return await getattr(self, f"async_step_{next_step_id}")(user_input={})

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.BaseFirmwareOptionsFlow.async_step_pick_firmware_zigbee",
            autospec=True,
            side_effect=mock_async_step_pick_firmware_zigbee,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.BaseFirmwareInstallFlow._ensure_thread_addon_setup",
            return_value=None,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.BaseFirmwareInstallFlow._install_firmware_step",
            autospec=True,
            side_effect=mock_install_firmware_step,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.probe_silabs_firmware_info",
            return_value=FirmwareInfo(
                device=RADIO_DEVICE,
                firmware_type=fw_type,
                firmware_version=fw_version,
                owners=[],
                source="probe",
            ),
        ),
    ):
        confirm_result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": step},
        )

        assert confirm_result["type"] is FlowResultType.FORM
        assert confirm_result["step_id"] == (
            "confirm_zigbee" if step == STEP_PICK_FIRMWARE_ZIGBEE else "confirm_otbr"
        )

        create_result = await hass.config_entries.options.async_configure(
            confirm_result["flow_id"], user_input={}
        )

    assert create_result["type"] is FlowResultType.CREATE_ENTRY

    assert config_entry.data == {
        "firmware": fw_type.value,
        "firmware_version": fw_version,
    }


@pytest.mark.usefixtures("supervisor_client")
async def test_options_flow_multipan_uninstall(hass: HomeAssistant) -> None:
    """Test options flow for when multi-PAN firmware is installed."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    config_entry = MockConfigEntry(
        data={"firmware": ApplicationType.CPC},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    # Multi-PAN addon is running
    mock_multipan_manager = Mock(spec_set=await get_multiprotocol_addon_manager(hass))
    mock_multipan_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname=None,
        options={"device": RADIO_DEVICE},
        state=AddonState.RUNNING,
        update_available=False,
        version="1.0.0",
    )

    mock_flasher_manager = Mock(spec_set=get_flasher_addon_manager(hass))
    mock_flasher_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_RUNNING,
        update_available=False,
        version="1.0.0",
    )

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.get_multiprotocol_addon_manager",
            return_value=mock_multipan_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.get_flasher_addon_manager",
            return_value=mock_flasher_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "main_menu"
        assert "multipan_settings" in result["menu_options"]

        # Pick multi-PAN settings
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": "multipan_settings"},
        )

        # Pick the uninstall option
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": "uninstall_addon"},
        )

        # Check the box
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_DISABLE_MULTI_PAN: True}
        )

        # Finish the flow
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        await hass.async_block_till_done(wait_background_tasks=True)
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        await hass.async_block_till_done(wait_background_tasks=True)
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.CREATE_ENTRY

    # We've reverted the firmware back to Zigbee
    assert config_entry.data["firmware"] == "ezsp"
