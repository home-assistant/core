"""Test the Home Assistant hardware firmware config flow failure cases."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
import pytest

from homeassistant.components.hassio import AddonError
from homeassistant.components.homeassistant_hardware.firmware_config_flow import (
    STEP_PICK_FIRMWARE_THREAD,
    STEP_PICK_FIRMWARE_ZIGBEE,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningAddon,
    OwningIntegration,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .test_config_flow import (
    TEST_DEVICE,
    TEST_DOMAIN,
    TEST_HARDWARE_NAME,
    consume_progress_flow,
    mock_firmware_info,
    mock_test_firmware_platform,  # noqa: F401
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def fixture_mock_supervisor_client(supervisor_client: AsyncMock):
    """Mock supervisor client in tests."""


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
@pytest.mark.usefixtures("addon_store_info")
async def test_config_flow_cannot_probe_firmware_zigbee(hass: HomeAssistant) -> None:
    """Test failure case when firmware cannot be probed for zigbee."""

    with mock_firmware_info(
        probe_app_type=None,
    ):
        # Start the flow
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": "hardware"}
        )

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "pick_firmware"

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

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "unsupported_firmware"


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
async def test_cannot_probe_after_install_zigbee(hass: HomeAssistant) -> None:
    """Test unsupported firmware after firmware install for Zigbee."""
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

    with mock_firmware_info(
        probe_app_type=None,
        flash_app_type=ApplicationType.EZSP,
    ):
        create_result = await consume_progress_flow(
            hass,
            flow_id=pick_result["flow_id"],
            valid_step_ids=("install_zigbee_firmware",),
        )

    assert create_result["type"] is FlowResultType.ABORT
    assert create_result["reason"] == "unsupported_firmware"


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
@pytest.mark.usefixtures("addon_store_info")
async def test_config_flow_cannot_probe_firmware_thread(hass: HomeAssistant) -> None:
    """Test failure case when firmware cannot be probed for thread."""

    with mock_firmware_info(
        probe_app_type=None,
    ):
        # Start the flow
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": "hardware"}
        )

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "pick_firmware"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "unsupported_firmware"


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
@pytest.mark.usefixtures("addon_installed")
async def test_cannot_probe_after_install_thread(hass: HomeAssistant) -> None:
    """Test unsupported firmware after firmware install for thread."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        probe_app_type=ApplicationType.EZSP,
        flash_app_type=ApplicationType.SPINEL,
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

    with mock_firmware_info(
        probe_app_type=None,
        flash_app_type=ApplicationType.SPINEL,
    ):
        # Progress the flow, it is now installing firmware
        result = await consume_progress_flow(
            hass,
            flow_id=pick_result["flow_id"],
            valid_step_ids=(
                "pick_firmware_thread",
                "install_otbr_addon",
                "install_thread_firmware",
                "start_otbr_addon",
            ),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_firmware"


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
async def test_config_flow_thread_not_hassio(hass: HomeAssistant) -> None:
    """Test when the stick is used with a non-hassio setup and Thread is selected."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        is_hassio=False,
        probe_app_type=ApplicationType.EZSP,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "not_hassio_thread"


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
async def test_config_flow_thread_addon_info_fails(
    hass: HomeAssistant,
    addon_store_info: AsyncMock,
) -> None:
    """Test addon info fails before firmware install."""

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        probe_app_type=ApplicationType.EZSP,
    ):
        addon_store_info.side_effect = AddonError()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        # Cannot get addon info
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "addon_info_failed"


@pytest.mark.usefixtures("addon_not_installed")
@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
async def test_config_flow_thread_addon_install_fails(
    hass: HomeAssistant,
    install_addon: AsyncMock,
) -> None:
    """Test failure case when flasher addon cannot be installed."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        probe_app_type=ApplicationType.EZSP,
    ):
        install_addon.side_effect = AddonError()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "install_thread_firmware"
        assert result["progress_action"] == "install_firmware"

        result = await consume_progress_flow(
            hass,
            flow_id=result["flow_id"],
            valid_step_ids=(
                "install_otbr_addon",
                "install_thread_firmware",
            ),
        )

        # Cannot install addon
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "addon_install_failed"


@pytest.mark.usefixtures("addon_installed")
@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
async def test_config_flow_thread_addon_set_config_fails(
    hass: HomeAssistant,
    set_addon_options: AsyncMock,
) -> None:
    """Test failure case when flasher addon cannot be configured."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        probe_app_type=ApplicationType.EZSP,
    ):
        set_addon_options.side_effect = AddonError()

        pick_thread_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        pick_thread_progress_result = await consume_progress_flow(
            hass,
            flow_id=pick_thread_result["flow_id"],
            valid_step_ids=(
                "pick_firmware_thread",
                "install_thread_firmware",
                "start_otbr_addon",
            ),
        )

        assert pick_thread_progress_result["type"] == FlowResultType.ABORT
        assert pick_thread_progress_result["reason"] == "addon_set_config_failed"


@pytest.mark.usefixtures("addon_installed")
@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
async def test_config_flow_thread_flasher_run_fails(
    hass: HomeAssistant,
    start_addon: AsyncMock,
) -> None:
    """Test failure case when flasher addon fails to run."""
    start_addon.side_effect = AddonError()
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        probe_app_type=ApplicationType.EZSP,
    ):
        pick_thread_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        pick_thread_progress_result = await consume_progress_flow(
            hass,
            flow_id=pick_thread_result["flow_id"],
            valid_step_ids=(
                "pick_firmware_thread",
                "install_thread_firmware",
                "start_otbr_addon",
            ),
        )

        assert pick_thread_progress_result["type"] == FlowResultType.ABORT
        assert pick_thread_progress_result["reason"] == "addon_start_failed"


@pytest.mark.usefixtures("addon_running")
@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
async def test_config_flow_thread_confirmation_fails(hass: HomeAssistant) -> None:
    """Test the config flow failing due to OpenThread firmware not being detected."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        probe_app_type=ApplicationType.EZSP,
        flash_app_type=None,
    ):
        pick_thread_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        pick_thread_progress_result = await consume_progress_flow(
            hass,
            flow_id=pick_thread_result["flow_id"],
            valid_step_ids=(
                "pick_firmware_thread",
                "install_thread_firmware",
                "start_otbr_addon",
            ),
        )

        assert pick_thread_progress_result["type"] is FlowResultType.ABORT
        assert pick_thread_progress_result["reason"] == "fw_install_failed"


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains", ["test_firmware_domain"]
)
async def test_config_flow_firmware_index_download_fails_and_required(
    hass: HomeAssistant,
) -> None:
    """Test flow aborts if OTA index download fails and install is required."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        # The wrong firmware is installed, so a new install is required
        probe_app_type=ApplicationType.SPINEL,
    ) as mock_update_client:
        mock_update_client.async_update_data.side_effect = ClientError()

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

        assert pick_result["type"] is FlowResultType.ABORT
        assert pick_result["reason"] == "fw_download_failed"


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains", ["test_firmware_domain"]
)
async def test_config_flow_firmware_download_fails_and_required(
    hass: HomeAssistant,
) -> None:
    """Test flow aborts if firmware download fails and install is required."""
    init_result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": "hardware"}
    )

    assert init_result["type"] is FlowResultType.MENU
    assert init_result["step_id"] == "pick_firmware"

    with mock_firmware_info(
        # The wrong firmware is installed, so a new install is required
        probe_app_type=ApplicationType.SPINEL,
    ) as mock_update_client:
        mock_update_client.async_fetch_firmware.side_effect = ClientError()

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

        assert pick_result["type"] is FlowResultType.ABORT
        assert pick_result["reason"] == "fw_download_failed"


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
async def test_options_flow_zigbee_to_thread_zha_configured(
    hass: HomeAssistant,
) -> None:
    """Test the options flow migration failure, ZHA using the stick."""
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

    # Pretend ZHA is using the stick
    with patch(
        "homeassistant.components.homeassistant_hardware.firmware_config_flow.guess_hardware_owners",
        return_value=[
            FirmwareInfo(
                device=TEST_DEVICE,
                firmware_type=ApplicationType.EZSP,
                firmware_version="1.2.3.4",
                source="zha",
                owners=[OwningIntegration(config_entry_id="some_config_entry_id")],
            )
        ],
    ):
        # Confirm options flow
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        # Pick Thread
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "zha_still_using_stick"


@pytest.mark.parametrize(
    "ignore_translations_for_mock_domains",
    ["test_firmware_domain"],
)
async def test_options_flow_thread_to_zigbee_otbr_configured(
    hass: HomeAssistant,
) -> None:
    """Test the options flow migration failure, OTBR still using the stick."""
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

    # Confirm options flow
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Pretend OTBR is using the stick
    with patch(
        "homeassistant.components.homeassistant_hardware.firmware_config_flow.guess_hardware_owners",
        return_value=[
            FirmwareInfo(
                device=TEST_DEVICE,
                firmware_type=ApplicationType.EZSP,
                firmware_version="1.2.3.4",
                source="otbr",
                owners=[OwningAddon(slug="openthread_border_router")],
            )
        ],
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "otbr_still_using_stick"
