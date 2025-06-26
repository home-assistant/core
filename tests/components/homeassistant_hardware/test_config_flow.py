"""Test the Home Assistant hardware firmware config flow."""

import asyncio
from collections.abc import Awaitable, Callable, Generator, Iterator
import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

from ha_silabs_firmware_client import (
    FirmwareManifest,
    FirmwareMetadata,
    FirmwareUpdateClient,
)
import pytest
from yarl import URL

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
)
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

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
TEST_RELEASES_URL = URL("http://invalid/releases")


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

    async def async_step_install_zigbee_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Zigbee firmware."""
        return await self._install_firmware_step(
            fw_update_url=TEST_RELEASES_URL,
            fw_type="fake_zigbee_ncp",
            firmware_name="Zigbee",
            expected_installed_firmware_type=ApplicationType.EZSP,
            step_id="install_zigbee_firmware",
            next_step_id="confirm_zigbee",
        )

    async def async_step_install_thread_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Thread firmware."""
        return await self._install_firmware_step(
            fw_update_url=TEST_RELEASES_URL,
            fw_type="fake_openthread_rcp",
            firmware_name="Thread",
            expected_installed_firmware_type=ApplicationType.SPINEL,
            step_id="install_thread_firmware",
            next_step_id="start_otbr_addon",
        )

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

    async def async_step_install_zigbee_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Zigbee firmware."""
        return await self.async_step_confirm_zigbee()

    async def async_step_install_thread_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Thread firmware."""
        return await self.async_step_start_otbr_addon()

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


def create_mock_owner() -> Mock:
    """Mock for OwningAddon / OwningIntegration."""
    owner = Mock()
    owner.is_running = AsyncMock(return_value=True)
    owner.temporarily_stop = MagicMock()
    owner.temporarily_stop.return_value.__aenter__.return_value = AsyncMock()

    return owner


@contextlib.contextmanager
def mock_firmware_info(
    hass: HomeAssistant,
    *,
    is_hassio: bool = True,
    probe_app_type: ApplicationType | None = ApplicationType.EZSP,
    otbr_addon_info: AddonInfo = AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_INSTALLED,
        update_available=False,
        version=None,
    ),
    flash_app_type: ApplicationType = ApplicationType.EZSP,
) -> Iterator[tuple[Mock, Mock]]:
    """Mock the main addon states for the config flow."""
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

    mock_update_client = AsyncMock(spec_set=FirmwareUpdateClient)
    mock_update_client.async_update_data.return_value = FirmwareManifest(
        url=TEST_RELEASES_URL,
        html_url=TEST_RELEASES_URL / "html",
        created_at=utcnow(),
        firmwares=[
            FirmwareMetadata(
                filename="fake_openthread_rcp_7.4.4.0_variant.gbl",
                checksum="sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                size=123,
                release_notes="Some release notes",
                metadata={},
                url=TEST_RELEASES_URL / "fake_openthread_rcp_7.4.4.0_variant.gbl",
            ),
            FirmwareMetadata(
                filename="fake_zigbee_ncp_7.4.4.0_variant.gbl",
                checksum="sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                size=123,
                release_notes="Some release notes",
                metadata={},
                url=TEST_RELEASES_URL / "fake_zigbee_ncp_7.4.4.0_variant.gbl",
            ),
        ],
    )

    if probe_app_type is None:
        probed_firmware_info = None
    else:
        probed_firmware_info = FirmwareInfo(
            device="/dev/ttyUSB0",  # Not used
            firmware_type=probe_app_type,
            firmware_version=None,
            owners=[],
            source="probe",
        )

    if flash_app_type is None:
        flashed_firmware_info = None
    else:
        flashed_firmware_info = FirmwareInfo(
            device=TEST_DEVICE,
            firmware_type=flash_app_type,
            firmware_version="7.4.4.0",
            owners=[create_mock_owner()],
            source="probe",
        )

    async def mock_flash_firmware(
        hass: HomeAssistant,
        device: str,
        fw_data: bytes,
        expected_installed_firmware_type: ApplicationType,
        bootloader_reset_type: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> FirmwareInfo:
        await asyncio.sleep(0)
        progress_callback(0, 100)
        await asyncio.sleep(0)
        progress_callback(50, 100)
        await asyncio.sleep(0)
        progress_callback(100, 100)

        if flashed_firmware_info is None:
            raise HomeAssistantError("Failed to probe the firmware after flashing")

        return flashed_firmware_info

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
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.is_hassio",
            return_value=is_hassio,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.is_hassio",
            return_value=is_hassio,
        ),
        patch(
            # We probe once before installation and once after
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.probe_silabs_firmware_info",
            side_effect=(probed_firmware_info, flashed_firmware_info),
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.FirmwareUpdateClient",
            return_value=mock_update_client,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.parse_firmware_image"
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.async_flash_silabs_firmware",
            side_effect=mock_flash_firmware,
        ),
    ):
        yield mock_otbr_manager


async def consume_progress_flow(
    hass: HomeAssistant,
    flow_id: str,
    valid_step_ids: tuple[str],
) -> ConfigFlowResult:
    """Consume a progress flow until it is done."""
    while True:
        result = await hass.config_entries.flow.async_configure(flow_id)
        flow_id = result["flow_id"]

        if result["type"] != FlowResultType.SHOW_PROGRESS:
            break

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] in valid_step_ids

        await asyncio.sleep(0.1)

    return result


async def test_config_flow_zigbee(hass: HomeAssistant) -> None:
    """Test the config flow."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        hass,
        probe_app_type=ApplicationType.SPINEL,
        flash_app_type=ApplicationType.EZSP,
    ):
        # Pick the menu option: we are flashing the firmware
        pick_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert pick_result["type"] is FlowResultType.SHOW_PROGRESS
        assert pick_result["progress_action"] == "install_firmware"
        assert pick_result["step_id"] == "install_zigbee_firmware"

        confirm_result = await consume_progress_flow(
            hass,
            flow_id=pick_result["flow_id"],
            valid_step_ids=("install_zigbee_firmware",),
        )

        assert confirm_result["type"] is FlowResultType.FORM
        assert confirm_result["step_id"] == "confirm_zigbee"

        create_result = await hass.config_entries.flow.async_configure(
            confirm_result["flow_id"], user_input={}
        )
        assert create_result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = create_result["result"]
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

    with mock_firmware_info(hass, probe_app_type=ApplicationType.SPINEL):
        # Pick the menu option: we skip installation, instead we directly run it
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        # Confirm
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Done
    with mock_firmware_info(
        hass,
        probe_app_type=ApplicationType.EZSP,
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
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        hass,
        probe_app_type=ApplicationType.EZSP,
        flash_app_type=ApplicationType.SPINEL,
    ) as mock_otbr_manager:
        # Pick the menu option
        pick_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        assert pick_result["type"] is FlowResultType.SHOW_PROGRESS
        assert pick_result["progress_action"] == "install_addon"
        assert pick_result["step_id"] == "install_otbr_addon"
        assert pick_result["description_placeholders"]["firmware_type"] == "ezsp"
        assert pick_result["description_placeholders"]["model"] == TEST_HARDWARE_NAME

        await hass.async_block_till_done(wait_background_tasks=True)

        mock_otbr_manager.async_get_addon_info.return_value = AddonInfo(
            available=True,
            hostname=None,
            options={
                "device": "",
                "baudrate": 460800,
                "flow_control": True,
                "autoflash_firmware": False,
            },
            state=AddonState.NOT_RUNNING,
            update_available=False,
            version="1.2.3",
        )

        # Progress the flow, it is now installing firmware
        confirm_otbr_result = await consume_progress_flow(
            hass,
            flow_id=pick_result["flow_id"],
            valid_step_ids=(
                "pick_firmware_thread",
                "install_otbr_addon",
                "install_thread_firmware",
                "start_otbr_addon",
            ),
        )

        # Installation will conclude with the config entry being created
        create_result = await hass.config_entries.flow.async_configure(
            confirm_otbr_result["flow_id"], user_input={}
        )
        assert create_result["type"] is FlowResultType.CREATE_ENTRY

        config_entry = create_result["result"]
        assert config_entry.data == {
            "firmware": "spinel",
            "device": TEST_DEVICE,
            "hardware": TEST_HARDWARE_NAME,
        }

        assert mock_otbr_manager.async_set_addon_options.mock_calls == [
            call(
                {
                    "device": TEST_DEVICE,
                    "baudrate": 460800,
                    "flow_control": True,
                    "autoflash_firmware": False,
                }
            )
        ]


async def test_config_flow_thread_addon_already_installed(hass: HomeAssistant) -> None:
    """Test the Thread config flow, addon is already installed."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    with mock_firmware_info(
        hass,
        probe_app_type=ApplicationType.EZSP,
        flash_app_type=ApplicationType.SPINEL,
        otbr_addon_info=AddonInfo(
            available=True,
            hostname=None,
            options={},
            state=AddonState.NOT_RUNNING,
            update_available=False,
            version=None,
        ),
    ) as mock_otbr_manager:
        # Pick the menu option
        pick_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        # Progress
        confirm_otbr_result = await consume_progress_flow(
            hass,
            flow_id=pick_result["flow_id"],
            valid_step_ids=(
                "pick_firmware_thread",
                "install_thread_firmware",
                "start_otbr_addon",
            ),
        )

        # We're now waiting to confirm OTBR
        assert confirm_otbr_result["type"] is FlowResultType.FORM
        assert confirm_otbr_result["step_id"] == "confirm_otbr"

        # The addon has been installed
        assert mock_otbr_manager.async_set_addon_options.mock_calls == [
            call(
                {
                    "device": TEST_DEVICE,
                    "baudrate": 460800,
                    "flow_control": True,
                    "autoflash_firmware": False,  # And firmware flashing is disabled
                }
            )
        ]

        # Finally, create the config entry
        create_result = await hass.config_entries.flow.async_configure(
            confirm_otbr_result["flow_id"], user_input={}
        )
        assert create_result["type"] is FlowResultType.CREATE_ENTRY
        assert create_result["result"].data == {
            "firmware": "spinel",
            "device": TEST_DEVICE,
            "hardware": TEST_HARDWARE_NAME,
        }


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

    with mock_firmware_info(
        hass,
        probe_app_type=ApplicationType.EZSP,
        flash_app_type=ApplicationType.SPINEL,
    ) as mock_otbr_manager:
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
                "autoflash_firmware": False,
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
                    "autoflash_firmware": False,
                }
            )
        ]

        await hass.async_block_till_done(wait_background_tasks=True)

        # The addon is now running
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_otbr"

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

    with mock_firmware_info(
        hass,
        probe_app_type=ApplicationType.SPINEL,
    ):
        # Pick the menu option: we are now installing the addon
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        result = await hass.config_entries.options.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_zigbee"

    with mock_firmware_info(
        hass,
        probe_app_type=ApplicationType.EZSP,
    ):
        # We are now done
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        # The firmware type has been updated
        assert config_entry.data["firmware"] == "ezsp"
