"""Test the Home Assistant hardware firmware config flow."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterator, Sequence
import contextlib
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

from aiohasupervisor.models import AddonsOptions
from aiohttp import ClientError
from ha_silabs_firmware_client import (
    FirmwareManifest,
    FirmwareMetadata,
    FirmwareUpdateClient,
)
import pytest
from yarl import URL

from homeassistant.components.homeassistant_hardware.firmware_config_flow import (
    STEP_PICK_FIRMWARE_THREAD,
    STEP_PICK_FIRMWARE_ZIGBEE,
    BaseFirmwareConfigFlow,
    BaseFirmwareOptionsFlow,
)
from homeassistant.components.homeassistant_hardware.helpers import (
    async_firmware_update_context,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    ResetTarget,
)
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_USER,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import (
    ANY,
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

_LOGGER = logging.getLogger(__name__)

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
            fw_update_url=str(TEST_RELEASES_URL),
            fw_type="fake_zigbee_ncp",
            firmware_name="Zigbee",
            expected_installed_firmware_type=ApplicationType.EZSP,
            step_id="install_zigbee_firmware",
            next_step_id="pre_confirm_zigbee",
        )

    async def async_step_install_thread_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Thread firmware."""
        return await self._install_firmware_step(
            fw_update_url=str(TEST_RELEASES_URL),
            fw_type="fake_openthread_rcp",
            firmware_name="Thread",
            expected_installed_firmware_type=ApplicationType.SPINEL,
            step_id="install_thread_firmware",
            next_step_id="finish_thread_installation",
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
        return await self._install_firmware_step(
            fw_update_url=str(TEST_RELEASES_URL),
            fw_type="fake_zigbee_ncp",
            firmware_name="Zigbee",
            expected_installed_firmware_type=ApplicationType.EZSP,
            step_id="install_zigbee_firmware",
            next_step_id="pre_confirm_zigbee",
        )

    async def async_step_install_thread_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Thread firmware."""
        return await self._install_firmware_step(
            fw_update_url=str(TEST_RELEASES_URL),
            fw_type="fake_openthread_rcp",
            firmware_name="Thread",
            expected_installed_firmware_type=ApplicationType.SPINEL,
            step_id="install_thread_firmware",
            next_step_id="finish_thread_installation",
        )

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
) -> AsyncGenerator[None]:
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
    *,
    is_hassio: bool = True,
    probe_app_type: ApplicationType | None = ApplicationType.EZSP,
    probe_fw_version: str | None = "2.4.4.0",
    flash_app_type: ApplicationType = ApplicationType.EZSP,
    flash_fw_version: str | None = "7.4.4.0",
) -> Iterator[Mock]:
    """Mock the firmware info."""
    mock_update_client = AsyncMock(spec_set=FirmwareUpdateClient)
    mock_update_client.async_update_data.return_value = FirmwareManifest(
        url=TEST_RELEASES_URL,
        html_url=TEST_RELEASES_URL / "html",
        created_at=utcnow(),
        firmwares=(
            FirmwareMetadata(
                filename="fake_openthread_rcp_7.4.4.0_variant.gbl",
                checksum="sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                size=123,
                release_notes="Some release notes",
                metadata={
                    "baudrate": 460800,
                    "fw_type": "openthread_rcp",
                    "fw_variant": None,
                    "metadata_version": 2,
                    "ot_rcp_version": "SL-OPENTHREAD/2.4.4.0_GitHub-7074a43e4",
                    "sdk_version": "4.4.4",
                },
                url=TEST_RELEASES_URL / "fake_openthread_rcp_7.4.4.0_variant.gbl",
            ),
            FirmwareMetadata(
                filename="fake_zigbee_ncp_7.4.4.0_variant.gbl",
                checksum="sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                size=123,
                release_notes="Some release notes",
                metadata={
                    "baudrate": 115200,
                    "ezsp_version": "7.4.4.0",
                    "fw_type": "zigbee_ncp",
                    "fw_variant": None,
                    "metadata_version": 2,
                    "sdk_version": "4.4.4",
                },
                url=TEST_RELEASES_URL / "fake_zigbee_ncp_7.4.4.0_variant.gbl",
            ),
        ),
    )

    if probe_app_type is None:
        probed_firmware_info = None
    else:
        probed_firmware_info = FirmwareInfo(
            device="/dev/ttyUSB0",  # Not used
            firmware_type=probe_app_type,
            firmware_version=probe_fw_version,
            owners=[],
            source="probe",
        )

    if flash_app_type is None:
        flashed_firmware_info = None
    else:
        flashed_firmware_info = FirmwareInfo(
            device=TEST_DEVICE,
            firmware_type=flash_app_type,
            firmware_version=flash_fw_version,
            owners=[create_mock_owner()],
            source="probe",
        )

    async def mock_flash_firmware(
        hass: HomeAssistant,
        device: str,
        fw_data: bytes,
        expected_installed_firmware_type: ApplicationType,
        bootloader_reset_methods: Sequence[ResetTarget] = (),
        progress_callback: Callable[[int, int], None] | None = None,
        *,
        domain: str = "homeassistant_hardware",
    ) -> FirmwareInfo:
        async with async_firmware_update_context(hass, device, domain):
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
        yield mock_update_client


async def consume_progress_flow(
    hass: HomeAssistant,
    flow_id: str,
    valid_step_ids: tuple[str, ...],
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


async def test_config_flow_zigbee_recommended(hass: HomeAssistant) -> None:
    """Test flow with recommended Zigbee installation type."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        probe_app_type=ApplicationType.SPINEL,
        flash_app_type=ApplicationType.EZSP,
    ):
        # Pick the menu option: we are flashing the firmware
        pick_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert pick_result["type"] is FlowResultType.MENU
        assert pick_result["step_id"] == "zigbee_installation_type"

        pick_result = await hass.config_entries.flow.async_configure(
            pick_result["flow_id"],
            user_input={"next_step_id": "zigbee_intent_recommended"},
        )

        assert pick_result["type"] is FlowResultType.SHOW_PROGRESS
        assert pick_result["progress_action"] == "install_firmware"
        assert pick_result["step_id"] == "install_zigbee_firmware"

        create_result = await consume_progress_flow(
            hass,
            flow_id=pick_result["flow_id"],
            valid_step_ids=("install_zigbee_firmware",),
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

    progress_zha_flows = hass.config_entries.flow._async_progress_by_handler(
        handler="zha",
        match_context=None,
    )

    assert len(progress_zha_flows) == 1

    progress_zha_flow = progress_zha_flows[0]
    assert progress_zha_flow.init_data == {
        "name": "Some Hardware Name",
        "port": {
            "path": "/dev/SomeDevice123",
            "baudrate": 115200,
            "flow_control": "hardware",
        },
        "radio_type": "ezsp",
        "flow_strategy": "recommended",
    }


async def test_config_flow_zigbee_custom_zha(hass: HomeAssistant) -> None:
    """Test flow with custom Zigbee installation type and ZHA selected."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        probe_app_type=ApplicationType.SPINEL,
        flash_app_type=ApplicationType.EZSP,
    ):
        # Pick the menu option: we are flashing the firmware
        pick_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert pick_result["type"] is FlowResultType.MENU
        assert pick_result["step_id"] == "zigbee_installation_type"

        pick_result = await hass.config_entries.flow.async_configure(
            pick_result["flow_id"],
            user_input={"next_step_id": "zigbee_intent_custom"},
        )

        assert pick_result["type"] is FlowResultType.MENU
        assert pick_result["step_id"] == "zigbee_integration"

        pick_result = await hass.config_entries.flow.async_configure(
            pick_result["flow_id"],
            user_input={"next_step_id": "zigbee_integration_zha"},
        )

        assert pick_result["type"] is FlowResultType.SHOW_PROGRESS
        assert pick_result["progress_action"] == "install_firmware"
        assert pick_result["step_id"] == "install_zigbee_firmware"

        create_result = await consume_progress_flow(
            hass,
            flow_id=pick_result["flow_id"],
            valid_step_ids=("install_zigbee_firmware",),
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
    assert flows == [
        {
            "context": {
                "confirm_only": True,
                "source": "hardware",
                "title_placeholders": {
                    "name": "Some Hardware Name",
                },
                "unique_id": "Some Hardware Name_ezsp_/dev/SomeDevice123",
            },
            "flow_id": ANY,
            "handler": "zha",
            "step_id": "confirm",
        }
    ]

    progress_zha_flows = hass.config_entries.flow._async_progress_by_handler(
        handler="zha",
        match_context=None,
    )

    assert len(progress_zha_flows) == 1

    progress_zha_flow = progress_zha_flows[0]
    assert progress_zha_flow.init_data == {
        "name": "Some Hardware Name",
        "port": {
            "path": "/dev/SomeDevice123",
            "baudrate": 115200,
            "flow_control": "hardware",
        },
        "radio_type": "ezsp",
        "flow_strategy": "advanced",
    }


async def test_config_flow_zigbee_custom_other(hass: HomeAssistant) -> None:
    """Test flow with custom Zigbee installation type and Other selected."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        probe_app_type=ApplicationType.SPINEL,
        flash_app_type=ApplicationType.EZSP,
    ):
        # Pick the menu option: we are flashing the firmware
        pick_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert pick_result["type"] is FlowResultType.MENU
        assert pick_result["step_id"] == "zigbee_installation_type"

        pick_result = await hass.config_entries.flow.async_configure(
            pick_result["flow_id"],
            user_input={"next_step_id": "zigbee_intent_custom"},
        )

        assert pick_result["type"] is FlowResultType.MENU
        assert pick_result["step_id"] == "zigbee_integration"

        pick_result = await hass.config_entries.flow.async_configure(
            pick_result["flow_id"],
            user_input={"next_step_id": "zigbee_integration_other"},
        )

        assert pick_result["type"] is FlowResultType.SHOW_PROGRESS
        assert pick_result["progress_action"] == "install_firmware"
        assert pick_result["step_id"] == "install_zigbee_firmware"

        create_result = await consume_progress_flow(
            hass,
            flow_id=pick_result["flow_id"],
            valid_step_ids=("install_zigbee_firmware",),
        )

        assert create_result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = create_result["result"]
    assert config_entry.data == {
        "firmware": "ezsp",
        "device": TEST_DEVICE,
        "hardware": TEST_HARDWARE_NAME,
    }

    flows = hass.config_entries.flow.async_progress()
    assert flows == []


async def test_config_flow_firmware_index_download_fails_but_not_required(
    hass: HomeAssistant,
) -> None:
    """Test flow continues if index download fails but install is not required."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        # The correct firmware is already installed
        probe_app_type=ApplicationType.EZSP,
        # An older version is probed, so an upgrade is attempted
        probe_fw_version="7.4.3.0",
    ) as mock_update_client:
        # Mock the firmware download to fail
        mock_update_client.async_update_data.side_effect = ClientError()

        pick_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert pick_result["type"] is FlowResultType.MENU
        assert pick_result["step_id"] == "zigbee_installation_type"

        result = await hass.config_entries.flow.async_configure(
            pick_result["flow_id"],
            user_input={"next_step_id": "zigbee_intent_recommended"},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_config_flow_firmware_download_fails_but_not_required(
    hass: HomeAssistant,
) -> None:
    """Test flow continues if firmware download fails but install is not required."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        # The correct firmware is already installed so installation isn't required
        probe_app_type=ApplicationType.EZSP,
        # An older version is probed, so an upgrade is attempted
        probe_fw_version="7.4.3.0",
    ) as mock_update_client:
        mock_update_client.async_fetch_firmware.side_effect = ClientError()

        pick_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert pick_result["type"] is FlowResultType.MENU
        assert pick_result["step_id"] == "zigbee_installation_type"

        result = await hass.config_entries.flow.async_configure(
            pick_result["flow_id"],
            user_input={"next_step_id": "zigbee_intent_recommended"},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_config_flow_doesnt_downgrade(
    hass: HomeAssistant,
) -> None:
    """Test flow exits early, without downgrading firmware."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with (
        mock_firmware_info(
            probe_app_type=ApplicationType.EZSP,
            # An newer version is probed than what we offer
            probe_fw_version="7.5.0.0",
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.async_flash_silabs_firmware"
        ) as mock_async_flash_silabs_firmware,
    ):
        pick_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert pick_result["type"] is FlowResultType.MENU
        assert pick_result["step_id"] == "zigbee_installation_type"

        result = await hass.config_entries.flow.async_configure(
            pick_result["flow_id"],
            user_input={"next_step_id": "zigbee_intent_recommended"},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert len(mock_async_flash_silabs_firmware.mock_calls) == 0


async def test_config_flow_zigbee_skip_step_if_installed(hass: HomeAssistant) -> None:
    """Test skip installing the firmware if not needed."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        probe_app_type=ApplicationType.SPINEL,
    ):
        # Pick the menu option: we skip installation, instead we directly run it
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "zigbee_installation_type"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": "zigbee_intent_recommended"},
        )

    # Done
    with mock_firmware_info(
        probe_app_type=ApplicationType.EZSP,
    ):
        await hass.async_block_till_done(wait_background_tasks=True)
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.CREATE_ENTRY


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


@pytest.mark.usefixtures("addon_installed")
async def test_config_flow_thread(
    hass: HomeAssistant,
    set_addon_options: AsyncMock,
    start_addon_with_otbr_discovery: AsyncMock,
) -> None:
    """Test the config flow and dataset push to OTBR."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    mock_dataset = "abcdabcdabcdabcdabcdab" * 10

    with (
        mock_firmware_info(
            probe_app_type=ApplicationType.EZSP,
            flash_app_type=ApplicationType.SPINEL,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.async_get_preferred_dataset",
            return_value=mock_dataset,
        ),
    ):
        # Pick the menu option
        pick_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        assert pick_result["type"] is FlowResultType.SHOW_PROGRESS
        assert pick_result["progress_action"] == "install_firmware"
        assert pick_result["step_id"] == "install_thread_firmware"
        description_placeholders = pick_result["description_placeholders"]
        assert description_placeholders is not None
        assert description_placeholders["firmware_type"] == "ezsp"
        assert description_placeholders["model"] == TEST_HARDWARE_NAME

        await hass.async_block_till_done(wait_background_tasks=True)

        # Progress the flow, it is now installing firmware
        create_result = await consume_progress_flow(
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
        assert create_result["type"] is FlowResultType.CREATE_ENTRY

        config_entry = create_result["result"]
        assert config_entry.data == {
            "firmware": "spinel",
            "device": TEST_DEVICE,
            "hardware": TEST_HARDWARE_NAME,
        }

        assert set_addon_options.call_args == call(
            "core_openthread_border_router",
            AddonsOptions(
                config={
                    "device": "/dev/SomeDevice123",
                    "baudrate": 460800,
                    "flow_control": True,
                    "autoflash_firmware": False,
                },
            ),
        )
        assert start_addon_with_otbr_discovery.call_count == 1
        assert start_addon_with_otbr_discovery.call_args == call(
            "core_openthread_border_router"
        )

        # Verify the preferred dataset was pushed to OTBR
        otbr_entries = hass.config_entries.async_entries("otbr")
        assert len(otbr_entries) == 1
        otbr_entry = otbr_entries[0]

        assert otbr_entry.runtime_data.set_active_dataset_tlvs.mock_calls == [
            call(bytes.fromhex(mock_dataset))
        ]
        assert otbr_entry.runtime_data.set_enabled.mock_calls == [call(True)]


@pytest.mark.usefixtures("addon_installed")
async def test_config_flow_thread_addon_already_installed(
    hass: HomeAssistant,
    set_addon_options: AsyncMock,
    start_addon_with_otbr_discovery: AsyncMock,
) -> None:
    """Test the Thread config flow, addon is already installed."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    with mock_firmware_info(
        probe_app_type=ApplicationType.EZSP,
        flash_app_type=ApplicationType.SPINEL,
    ):
        # Pick the menu option
        pick_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        # Progress
        create_result = await consume_progress_flow(
            hass,
            flow_id=pick_result["flow_id"],
            valid_step_ids=(
                "pick_firmware_thread",
                "install_thread_firmware",
                "start_otbr_addon",
            ),
        )

    # The add-on has been installed
    assert set_addon_options.call_args == call(
        "core_openthread_border_router",
        AddonsOptions(
            config={
                "device": "/dev/SomeDevice123",
                "baudrate": 460800,
                "flow_control": True,
                "autoflash_firmware": False,
            },
        ),
    )
    assert start_addon_with_otbr_discovery.call_count == 1
    assert start_addon_with_otbr_discovery.call_args == call(
        "core_openthread_border_router"
    )
    assert create_result["type"] is FlowResultType.CREATE_ENTRY
    assert create_result["result"].data == {
        "firmware": "spinel",
        "device": TEST_DEVICE,
        "hardware": TEST_HARDWARE_NAME,
    }


@pytest.mark.usefixtures("addon_not_installed")
async def test_options_flow_zigbee_to_thread(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon_with_otbr_discovery: AsyncMock,
) -> None:
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
        probe_app_type=ApplicationType.EZSP,
        flash_app_type=ApplicationType.SPINEL,
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "pick_firmware"
        description_placeholders = result["description_placeholders"]
        assert description_placeholders is not None
        assert description_placeholders["firmware_type"] == "ezsp"
        assert description_placeholders["model"] == TEST_HARDWARE_NAME

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "install_thread_firmware"
        assert result["progress_action"] == "install_firmware"

        await hass.async_block_till_done(wait_background_tasks=True)

        result = await hass.config_entries.options.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "install_otbr_addon"
        assert result["progress_action"] == "install_otbr_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        result = await hass.config_entries.options.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "start_otbr_addon"
        assert result["progress_action"] == "start_otbr_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        result = await hass.config_entries.options.async_configure(result["flow_id"])

    assert install_addon.call_count == 1
    assert install_addon.call_args == call("core_openthread_border_router")
    assert set_addon_options.call_count == 1
    assert set_addon_options.call_args == call(
        "core_openthread_border_router",
        AddonsOptions(
            config={
                "device": "/dev/SomeDevice123",
                "baudrate": 460800,
                "flow_control": True,
                "autoflash_firmware": False,
            },
        ),
    )
    assert start_addon_with_otbr_discovery.call_count == 1
    assert start_addon_with_otbr_discovery.call_args == call(
        "core_openthread_border_router"
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

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"
    description_placeholders = result["description_placeholders"]
    assert description_placeholders is not None
    assert description_placeholders["firmware_type"] == "spinel"
    assert description_placeholders["model"] == TEST_HARDWARE_NAME

    with mock_firmware_info(
        probe_app_type=ApplicationType.SPINEL,
    ):
        pick_result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert pick_result["type"] is FlowResultType.MENU
        assert pick_result["step_id"] == "zigbee_installation_type"

    with mock_firmware_info(
        probe_app_type=ApplicationType.EZSP,
    ):
        # We are now done
        result = await hass.config_entries.options.async_configure(
            pick_result["flow_id"],
            user_input={"next_step_id": "zigbee_intent_recommended"},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "install_zigbee_firmware"
        assert result["progress_action"] == "install_firmware"

        await hass.async_block_till_done(wait_background_tasks=True)

        create_result = await hass.config_entries.options.async_configure(
            result["flow_id"]
        )

        assert create_result["type"] is FlowResultType.CREATE_ENTRY

        # The firmware type has been updated
        assert config_entry.data["firmware"] == "ezsp"


async def test_config_flow_pick_firmware_shows_migrate_options_with_existing_zha(
    hass: HomeAssistant,
) -> None:
    """Test that migrate options are shown when ZHA entries exist."""
    # Create a ZHA config entry
    zha_entry = MockConfigEntry(
        domain="zha",
        data={"device": {"path": "/dev/ttyUSB1"}},
        title="ZHA",
    )
    zha_entry.add_to_hass(hass)

    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    # Should show migrate option for Zigbee since ZHA exists (migrating from ZHA to Zigbee)
    menu_options = init_result["menu_options"]
    assert "pick_firmware_zigbee_migrate" in menu_options
    assert "pick_firmware_thread" in menu_options  # Normal option for Thread


async def test_config_flow_pick_firmware_shows_migrate_options_with_existing_otbr(
    hass: HomeAssistant,
) -> None:
    """Test that migrate options are shown when OTBR entries exist."""
    # Create an OTBR config entry
    otbr_entry = MockConfigEntry(
        domain="otbr",
        data={"url": "http://192.168.1.100:8081"},
        title="OpenThread Border Router",
    )
    otbr_entry.add_to_hass(hass)

    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    # Should show migrate option for Thread since OTBR exists (migrating from OTBR to Thread)
    menu_options = init_result["menu_options"]
    assert "pick_firmware_thread_migrate" in menu_options
    assert "pick_firmware_zigbee" in menu_options  # Normal option for Zigbee


async def test_config_flow_pick_firmware_shows_migrate_options_with_both_existing(
    hass: HomeAssistant,
) -> None:
    """Test that migrate options are shown when both ZHA and OTBR entries exist."""
    # Create both ZHA and OTBR config entries
    zha_entry = MockConfigEntry(
        domain="zha",
        data={"device": {"path": "/dev/ttyUSB1"}},
        title="ZHA",
    )
    zha_entry.add_to_hass(hass)

    otbr_entry = MockConfigEntry(
        domain="otbr",
        data={"url": "http://192.168.1.100:8081"},
        title="OpenThread Border Router",
    )
    otbr_entry.add_to_hass(hass)

    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    # Should show migrate options for both since both exist
    menu_options = init_result["menu_options"]
    assert "pick_firmware_zigbee_migrate" in menu_options
    assert "pick_firmware_thread_migrate" in menu_options


async def test_config_flow_pick_firmware_shows_normal_options_without_existing(
    hass: HomeAssistant,
) -> None:
    """Test that normal options are shown when no ZHA or OTBR entries exist."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    # Should show normal options since no existing entries
    menu_options = init_result["menu_options"]
    assert "pick_firmware_zigbee" in menu_options
    assert "pick_firmware_thread" in menu_options
    assert "pick_firmware_zigbee_migrate" not in menu_options
    assert "pick_firmware_thread_migrate" not in menu_options


async def test_config_flow_zigbee_migrate_handler(hass: HomeAssistant) -> None:
    """Test that the Zigbee migrate handler works correctly."""
    # Ensure Zigbee migrate option is available by adding a ZHA entry
    zha_entry = MockConfigEntry(
        domain="zha",
        data={"device": {"path": "/dev/ttyUSB1"}},
        title="ZHA",
    )
    zha_entry.add_to_hass(hass)

    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    with mock_firmware_info(
        probe_app_type=ApplicationType.SPINEL,
        flash_app_type=ApplicationType.EZSP,
    ):
        # Test the migrate handler directly
        result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": "pick_firmware_zigbee_migrate"},
        )

        # Should proceed to zigbee installation type (same as normal zigbee flow)
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "zigbee_installation_type"


@pytest.mark.usefixtures("addon_installed")
async def test_config_flow_thread_migrate_handler(hass: HomeAssistant) -> None:
    """Test that the Thread migrate handler works correctly."""
    # Ensure Thread migrate option is available by adding an OTBR entry
    otbr_entry = MockConfigEntry(
        domain="otbr",
        data={"url": "http://192.168.1.100:8081"},
        title="OpenThread Border Router",
    )
    otbr_entry.add_to_hass(hass)

    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    with mock_firmware_info(
        probe_app_type=ApplicationType.EZSP,
        flash_app_type=ApplicationType.SPINEL,
    ):
        # Test the migrate handler directly
        result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": "pick_firmware_thread_migrate"},
        )

        # Should proceed to firmware install (same as normal thread flow)
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "install_firmware"
        assert result["step_id"] == "install_thread_firmware"


@pytest.mark.parametrize(
    ("zha_source", "otbr_source", "expected_menu"),
    [
        (
            SOURCE_USER,
            SOURCE_USER,
            ["pick_firmware_zigbee_migrate", "pick_firmware_thread_migrate"],
        ),
        (
            SOURCE_IGNORE,
            SOURCE_USER,
            ["pick_firmware_zigbee", "pick_firmware_thread_migrate"],
        ),
        (
            SOURCE_USER,
            SOURCE_IGNORE,
            ["pick_firmware_zigbee_migrate", "pick_firmware_thread"],
        ),
        (
            SOURCE_IGNORE,
            SOURCE_IGNORE,
            ["pick_firmware_zigbee", "pick_firmware_thread"],
        ),
    ],
)
async def test_config_flow_pick_firmware_with_ignored_entries(
    hass: HomeAssistant, zha_source: str, otbr_source: str, expected_menu: str
) -> None:
    """Test that ignored entries are properly excluded from migration menu options."""
    zha_entry = MockConfigEntry(
        domain="zha",
        data={"device": {"path": "/dev/ttyUSB1"}},
        title="ZHA",
        source=zha_source,
    )
    zha_entry.add_to_hass(hass)

    otbr_entry = MockConfigEntry(
        domain="otbr",
        data={"url": "http://192.168.1.100:8081"},
        title="OTBR",
        source=otbr_source,
    )
    otbr_entry.add_to_hass(hass)

    # Set up the flow
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    assert init_result["menu_options"] == expected_menu
