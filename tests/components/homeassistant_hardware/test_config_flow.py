"""Test the Home Assistant hardware firmware config flow."""

import asyncio
from collections.abc import Awaitable, Callable, Generator, Iterator
import contextlib
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from homeassistant.components.hassio import AddonInfo, AddonState
from homeassistant.components.homeassistant_hardware.firmware_config_flow import (
    STEP_PICK_FIRMWARE_THREAD,
    STEP_PICK_FIRMWARE_ZIGBEE,
    BaseFirmwareConfigFlow,
    BaseFirmwareOptionsFlow,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    get_otbr_addon_manager,
    get_zigbee_flasher_addon_manager,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test_firmware_domain"
TEST_DEVICE = "/dev/SomeDevice123"
TEST_HARDWARE_NAME = "Some Hardware Name"


class FakeFirmwareConfigFlow(BaseFirmwareConfigFlow, domain=TEST_DOMAIN):
    """Config flow for `test_firmware_domain`."""

    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        return FakeFirmwareOptionsFlowHandler(config_entry)

    async def async_step_hardware(
        self, data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle hardware flow."""
        self._device = TEST_DEVICE
        self._hardware_name = TEST_HARDWARE_NAME

        return await self.async_step_confirm()

    def _async_flow_finished(self) -> ConfigFlowResult:
        """Create the config entry."""
        assert self._device is not None
        assert self._hardware_name is not None
        assert self._probed_firmware_info is not None

        return self.async_create_entry(
            title=self._hardware_name,
            data={
                "device": self._device,
                "firmware": self._probed_firmware_info.firmware_type.value,
                "hardware": self._hardware_name,
            },
        )


class FakeFirmwareOptionsFlowHandler(BaseFirmwareOptionsFlow):
    """Options flow for `test_firmware_domain`."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Instantiate options flow."""
        super().__init__(*args, **kwargs)

        self._device = self.config_entry.data["device"]
        self._hardware_name = self.config_entry.data["hardware"]

        self._probed_firmware_info = FirmwareInfo(
            device=self._device,
            firmware_type=ApplicationType(self.config_entry.data["firmware"]),
            firmware_version=None,
            source="guess",
            owners=[],
        )

        # Regenerate the translation placeholders
        self._get_translation_placeholders()

    def _async_flow_finished(self) -> ConfigFlowResult:
        """Create the config entry."""
        assert self._probed_firmware_info is not None

        self.hass.config_entries.async_update_entry(
            entry=self.config_entry,
            data={
                **self.config_entry.data,
                "firmware": self._probed_firmware_info.firmware_type.value,
            },
            options=self.config_entry.options,
        )

        return self.async_create_entry(title="", data={})


@pytest.fixture(autouse=True)
async def mock_test_firmware_platform(
    hass: HomeAssistant,
) -> Generator[None]:
    """Fixture for a test config flow."""
    mock_module = MockModule(
        TEST_DOMAIN, async_setup_entry=AsyncMock(return_value=True)
    )
    mock_integration(hass, mock_module)
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    await async_setup_component(hass, "homeassistant_hardware", {})

    with mock_config_flow(TEST_DOMAIN, FakeFirmwareConfigFlow):
        yield


@pytest.fixture(autouse=True)
async def fixture_mock_supervisor_client(supervisor_client: AsyncMock):
    """Mock supervisor client in tests."""


def delayed_side_effect() -> Callable[..., Awaitable[None]]:
    """Slows down eager tasks by delaying for an event loop tick."""

    async def side_effect(*args: Any, **kwargs: Any) -> None:
        await asyncio.sleep(0)

    return side_effect


@contextlib.contextmanager
def mock_addon_info(
    hass: HomeAssistant,
    *,
    is_hassio: bool = True,
    app_type: ApplicationType | None = ApplicationType.EZSP,
    otbr_addon_info: AddonInfo = AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_INSTALLED,
        update_available=False,
        version=None,
    ),
    flasher_addon_info: AddonInfo = AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_INSTALLED,
        update_available=False,
        version=None,
    ),
) -> Iterator[tuple[Mock, Mock]]:
    """Mock the main addon states for the config flow."""
    mock_flasher_manager = Mock(spec_set=get_zigbee_flasher_addon_manager(hass))
    mock_flasher_manager.addon_name = "Silicon Labs Flasher"
    mock_flasher_manager.async_start_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_install_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_uninstall_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_get_addon_info.return_value = flasher_addon_info

    mock_otbr_manager = Mock(spec_set=get_otbr_addon_manager(hass))
    mock_otbr_manager.addon_name = "OpenThread Border Router"
    mock_otbr_manager.async_install_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_otbr_manager.async_uninstall_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_otbr_manager.async_start_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_otbr_manager.async_get_addon_info.return_value = otbr_addon_info

    if app_type is None:
        firmware_info_result = None
    else:
        firmware_info_result = FirmwareInfo(
            device="/dev/ttyUSB0",  # Not used
            firmware_type=app_type,
            firmware_version=None,
            owners=[],
            source="probe",
        )

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.get_otbr_addon_manager",
            return_value=mock_otbr_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.get_otbr_addon_manager",
            return_value=mock_otbr_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.get_zigbee_flasher_addon_manager",
            return_value=mock_flasher_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.is_hassio",
            return_value=is_hassio,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.is_hassio",
            return_value=is_hassio,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.probe_silabs_firmware_info",
            return_value=firmware_info_result,
        ),
    ):
        yield mock_otbr_manager, mock_flasher_manager


async def test_config_flow_zigbee(hass: HomeAssistant) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"

    with mock_addon_info(
        hass,
        app_type=ApplicationType.SPINEL,
    ) as (mock_otbr_manager, mock_flasher_manager):
        # Pick the menu option: we are now installing the addon
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "install_addon"
        assert result["step_id"] == "install_zigbee_flasher_addon"
        assert result["description_placeholders"]["firmware_type"] == "spinel"

        await hass.async_block_till_done(wait_background_tasks=True)

        # Progress the flow, we are now configuring the addon and running it
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "run_zigbee_flasher_addon"
        assert result["progress_action"] == "run_zigbee_flasher_addon"
        assert mock_flasher_manager.async_set_addon_options.mock_calls == [
            call(
                {
                    "device": TEST_DEVICE,
                    "baudrate": 115200,
                    "bootloader_baudrate": 115200,
                    "flow_control": True,
                }
            )
        ]

        await hass.async_block_till_done(wait_background_tasks=True)

        # Progress the flow, we are now uninstalling the addon
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "uninstall_zigbee_flasher_addon"
        assert result["progress_action"] == "uninstall_zigbee_flasher_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        # We are finally done with the addon
        assert mock_flasher_manager.async_uninstall_addon_waiting.mock_calls == [call()]

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_zigbee"

    with mock_addon_info(
        hass,
        app_type=ApplicationType.EZSP,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.data == {
        "firmware": "ezsp",
        "device": TEST_DEVICE,
        "hardware": TEST_HARDWARE_NAME,
    }

    # Ensure a ZHA discovery flow has been created
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    zha_flow = flows[0]
    assert zha_flow["handler"] == "zha"
    assert zha_flow["context"]["source"] == "hardware"
    assert zha_flow["step_id"] == "confirm"


async def test_config_flow_zigbee_skip_step_if_installed(hass: HomeAssistant) -> None:
    """Test the config flow, skip installing the addon if necessary."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"

    with mock_addon_info(
        hass,
        app_type=ApplicationType.SPINEL,
        flasher_addon_info=AddonInfo(
            available=True,
            hostname=None,
            options={
                "device": "",
                "baudrate": 115200,
                "bootloader_baudrate": 115200,
                "flow_control": True,
            },
            state=AddonState.NOT_RUNNING,
            update_available=False,
            version="1.2.3",
        ),
    ) as (mock_otbr_manager, mock_flasher_manager):
        # Pick the menu option: we skip installation, instead we directly run it
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "run_zigbee_flasher_addon"
        assert result["progress_action"] == "run_zigbee_flasher_addon"
        assert result["description_placeholders"]["firmware_type"] == "spinel"
        assert mock_flasher_manager.async_set_addon_options.mock_calls == [
            call(
                {
                    "device": TEST_DEVICE,
                    "baudrate": 115200,
                    "bootloader_baudrate": 115200,
                    "flow_control": True,
                }
            )
        ]

        # Uninstall the addon
        await hass.async_block_till_done(wait_background_tasks=True)
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Done
    with mock_addon_info(
        hass,
        app_type=ApplicationType.EZSP,
    ):
        await hass.async_block_till_done(wait_background_tasks=True)
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_zigbee"


async def test_config_flow_auto_confirm_if_running(hass: HomeAssistant) -> None:
    """Test the config flow skips the confirmation step the hardware is already used."""
    with patch(
        "homeassistant.components.homeassistant_hardware.firmware_config_flow.guess_firmware_info",
        return_value=FirmwareInfo(
            device=TEST_DEVICE,
            firmware_type=ApplicationType.EZSP,
            firmware_version="7.4.4.0",
            owners=[Mock(is_running=AsyncMock(return_value=True))],
            source="guess",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": "hardware"}
        )

    # There are no steps, the config entry is automatically created
    assert result["type"] is FlowResultType.CREATE_ENTRY
    config_entry = result["result"]
    assert config_entry.data == {
        "firmware": "ezsp",
        "device": TEST_DEVICE,
        "hardware": TEST_HARDWARE_NAME,
    }


async def test_config_flow_thread(hass: HomeAssistant) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"

    with mock_addon_info(
        hass,
        app_type=ApplicationType.EZSP,
    ) as (mock_otbr_manager, mock_flasher_manager):
        # Pick the menu option
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "install_addon"
        assert result["step_id"] == "install_otbr_addon"
        assert result["description_placeholders"]["firmware_type"] == "ezsp"
        assert result["description_placeholders"]["model"] == TEST_HARDWARE_NAME

        await hass.async_block_till_done(wait_background_tasks=True)

        mock_otbr_manager.async_get_addon_info.return_value = AddonInfo(
            available=True,
            hostname=None,
            options={
                "device": "",
                "baudrate": 460800,
                "flow_control": True,
                "autoflash_firmware": True,
            },
            state=AddonState.NOT_RUNNING,
            update_available=False,
            version="1.2.3",
        )

        # Progress the flow, it is now configuring the addon and running it
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "start_otbr_addon"
        assert result["progress_action"] == "start_otbr_addon"

        assert mock_otbr_manager.async_set_addon_options.mock_calls == [
            call(
                {
                    "device": TEST_DEVICE,
                    "baudrate": 460800,
                    "flow_control": True,
                    "autoflash_firmware": True,
                }
            )
        ]

        await hass.async_block_till_done(wait_background_tasks=True)

        # The addon is now running
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_otbr"

    with mock_addon_info(
        hass,
        app_type=ApplicationType.SPINEL,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        config_entry = result["result"]
        assert config_entry.data == {
            "firmware": "spinel",
            "device": TEST_DEVICE,
            "hardware": TEST_HARDWARE_NAME,
        }


async def test_config_flow_thread_addon_already_installed(hass: HomeAssistant) -> None:
    """Test the Thread config flow, addon is already installed."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    with mock_addon_info(
        hass,
        app_type=ApplicationType.EZSP,
        otbr_addon_info=AddonInfo(
            available=True,
            hostname=None,
            options={},
            state=AddonState.NOT_RUNNING,
            update_available=False,
            version=None,
        ),
    ) as (mock_otbr_manager, mock_flasher_manager):
        # Pick the menu option
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "start_otbr_addon"
        assert result["progress_action"] == "start_otbr_addon"

        assert mock_otbr_manager.async_set_addon_options.mock_calls == [
            call(
                {
                    "device": TEST_DEVICE,
                    "baudrate": 460800,
                    "flow_control": True,
                    "autoflash_firmware": True,
                }
            )
        ]

        await hass.async_block_till_done(wait_background_tasks=True)

        # The addon is now running
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_otbr"

    with mock_addon_info(
        hass,
        app_type=ApplicationType.SPINEL,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_config_flow_zigbee_not_hassio(hass: HomeAssistant) -> None:
    """Test when the stick is used with a non-hassio setup."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    with mock_addon_info(
        hass,
        is_hassio=False,
        app_type=ApplicationType.EZSP,
    ) as (mock_otbr_manager, mock_flasher_manager):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_zigbee"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.data == {
        "firmware": "ezsp",
        "device": TEST_DEVICE,
        "hardware": TEST_HARDWARE_NAME,
    }

    # Ensure a ZHA discovery flow has been created
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    zha_flow = flows[0]
    assert zha_flow["handler"] == "zha"
    assert zha_flow["context"]["source"] == "hardware"
    assert zha_flow["step_id"] == "confirm"


@pytest.mark.usefixtures("addon_store_info")
async def test_options_flow_zigbee_to_thread(hass: HomeAssistant) -> None:
    """Test the options flow, migrating Zigbee to Thread."""
    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "firmware": "ezsp",
            "device": TEST_DEVICE,
            "hardware": TEST_HARDWARE_NAME,
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)

    with mock_addon_info(
        hass,
        app_type=ApplicationType.EZSP,
    ) as (mock_otbr_manager, mock_flasher_manager):
        # First step is confirmation
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "pick_firmware"
        assert result["description_placeholders"]["firmware_type"] == "ezsp"
        assert result["description_placeholders"]["model"] == TEST_HARDWARE_NAME

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "install_addon"
        assert result["step_id"] == "install_otbr_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        mock_otbr_manager.async_get_addon_info.return_value = AddonInfo(
            available=True,
            hostname=None,
            options={
                "device": "",
                "baudrate": 460800,
                "flow_control": True,
                "autoflash_firmware": True,
            },
            state=AddonState.NOT_RUNNING,
            update_available=False,
            version="1.2.3",
        )

        # Progress the flow, it is now configuring the addon and running it
        result = await hass.config_entries.options.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "start_otbr_addon"
        assert result["progress_action"] == "start_otbr_addon"

        assert mock_otbr_manager.async_set_addon_options.mock_calls == [
            call(
                {
                    "device": TEST_DEVICE,
                    "baudrate": 460800,
                    "flow_control": True,
                    "autoflash_firmware": True,
                }
            )
        ]

        await hass.async_block_till_done(wait_background_tasks=True)

        # The addon is now running
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_otbr"

    with mock_addon_info(
        hass,
        app_type=ApplicationType.SPINEL,
    ):
        # We are now done
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        # The firmware type has been updated
        assert config_entry.data["firmware"] == "spinel"


@pytest.mark.usefixtures("addon_store_info")
async def test_options_flow_thread_to_zigbee(hass: HomeAssistant) -> None:
    """Test the options flow, migrating Thread to Zigbee."""
    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "firmware": "spinel",
            "device": TEST_DEVICE,
            "hardware": TEST_HARDWARE_NAME,
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)

    # First step is confirmation
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"
    assert result["description_placeholders"]["firmware_type"] == "spinel"
    assert result["description_placeholders"]["model"] == TEST_HARDWARE_NAME

    with mock_addon_info(
        hass,
        app_type=ApplicationType.SPINEL,
    ) as (mock_otbr_manager, mock_flasher_manager):
        # Pick the menu option: we are now installing the addon
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "install_addon"
        assert result["step_id"] == "install_zigbee_flasher_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        # Progress the flow, we are now configuring the addon and running it
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "run_zigbee_flasher_addon"
        assert result["progress_action"] == "run_zigbee_flasher_addon"
        assert mock_flasher_manager.async_set_addon_options.mock_calls == [
            call(
                {
                    "device": TEST_DEVICE,
                    "baudrate": 115200,
                    "bootloader_baudrate": 115200,
                    "flow_control": True,
                }
            )
        ]

        await hass.async_block_till_done(wait_background_tasks=True)

        # Progress the flow, we are now uninstalling the addon
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "uninstall_zigbee_flasher_addon"
        assert result["progress_action"] == "uninstall_zigbee_flasher_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        # We are finally done with the addon
        assert mock_flasher_manager.async_uninstall_addon_waiting.mock_calls == [call()]

        result = await hass.config_entries.options.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_zigbee"

    with mock_addon_info(
        hass,
        app_type=ApplicationType.EZSP,
    ):
        # We are now done
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        # The firmware type has been updated
        assert config_entry.data["firmware"] == "ezsp"
