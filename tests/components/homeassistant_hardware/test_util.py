"""Test hardware utilities."""

from unittest.mock import AsyncMock, patch

from universal_silabs_flasher.const import ApplicationType

from homeassistant.components.hassio import AddonError, AddonInfo, AddonState
from homeassistant.components.homeassistant_hardware.util import (
    FirmwareGuess,
    get_zha_device_path,
    guess_firmware_type,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ZHA_CONFIG_ENTRY = MockConfigEntry(
    domain="zha",
    unique_id="some_unique_id",
    data={
        "device": {
            "path": "socket://1.2.3.4:5678",
            "baudrate": 115200,
            "flow_control": None,
        },
        "radio_type": "ezsp",
    },
    version=4,
)


def test_get_zha_device_path() -> None:
    """Test extracting the ZHA device path from its config entry."""
    assert (
        get_zha_device_path(ZHA_CONFIG_ENTRY) == ZHA_CONFIG_ENTRY.data["device"]["path"]
    )


def test_get_zha_device_path_ignored_discovery() -> None:
    """Test extracting the ZHA device path from an ignored ZHA discovery."""
    config_entry = MockConfigEntry(
        domain="zha",
        unique_id="some_unique_id",
        data={},
        version=4,
    )

    assert get_zha_device_path(config_entry) is None


async def test_guess_firmware_type_unknown(hass: HomeAssistant) -> None:
    """Test guessing the firmware type."""

    assert (await guess_firmware_type(hass, "/dev/missing")) == FirmwareGuess(
        is_running=False, firmware_type=ApplicationType.EZSP, source="unknown"
    )


async def test_guess_firmware_type(hass: HomeAssistant) -> None:
    """Test guessing the firmware."""
    path = ZHA_CONFIG_ENTRY.data["device"]["path"]

    ZHA_CONFIG_ENTRY.add_to_hass(hass)

    ZHA_CONFIG_ENTRY.mock_state(hass, ConfigEntryState.NOT_LOADED)
    assert (await guess_firmware_type(hass, path)) == FirmwareGuess(
        is_running=False, firmware_type=ApplicationType.EZSP, source="zha"
    )

    # When ZHA is running, we indicate as such when guessing
    ZHA_CONFIG_ENTRY.mock_state(hass, ConfigEntryState.LOADED)
    assert (await guess_firmware_type(hass, path)) == FirmwareGuess(
        is_running=True, firmware_type=ApplicationType.EZSP, source="zha"
    )

    mock_otbr_addon_manager = AsyncMock()
    mock_multipan_addon_manager = AsyncMock()

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.util.is_hassio",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.get_otbr_addon_manager",
            return_value=mock_otbr_addon_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.get_multiprotocol_addon_manager",
            return_value=mock_multipan_addon_manager,
        ),
    ):
        mock_otbr_addon_manager.async_get_addon_info.side_effect = AddonError()
        mock_multipan_addon_manager.async_get_addon_info.side_effect = AddonError()

        # Hassio errors are ignored and we still go with ZHA
        assert (await guess_firmware_type(hass, path)) == FirmwareGuess(
            is_running=True, firmware_type=ApplicationType.EZSP, source="zha"
        )

        mock_otbr_addon_manager.async_get_addon_info.side_effect = None
        mock_otbr_addon_manager.async_get_addon_info.return_value = AddonInfo(
            available=True,
            hostname=None,
            options={"device": "/some/other/device"},
            state=AddonState.RUNNING,
            update_available=False,
            version="1.0.0",
        )

        # We will prefer ZHA, as it is running (and actually pointing to the device)
        assert (await guess_firmware_type(hass, path)) == FirmwareGuess(
            is_running=True, firmware_type=ApplicationType.EZSP, source="zha"
        )

        mock_otbr_addon_manager.async_get_addon_info.return_value = AddonInfo(
            available=True,
            hostname=None,
            options={"device": path},
            state=AddonState.NOT_RUNNING,
            update_available=False,
            version="1.0.0",
        )

        # We will still prefer ZHA, as it is the one actually running
        assert (await guess_firmware_type(hass, path)) == FirmwareGuess(
            is_running=True, firmware_type=ApplicationType.EZSP, source="zha"
        )

        mock_otbr_addon_manager.async_get_addon_info.return_value = AddonInfo(
            available=True,
            hostname=None,
            options={"device": path},
            state=AddonState.RUNNING,
            update_available=False,
            version="1.0.0",
        )

        # Finally, ZHA loses out to OTBR
        assert (await guess_firmware_type(hass, path)) == FirmwareGuess(
            is_running=True, firmware_type=ApplicationType.SPINEL, source="otbr"
        )

        mock_multipan_addon_manager.async_get_addon_info.side_effect = None
        mock_multipan_addon_manager.async_get_addon_info.return_value = AddonInfo(
            available=True,
            hostname=None,
            options={"device": path},
            state=AddonState.RUNNING,
            update_available=False,
            version="1.0.0",
        )

        # Which will lose out to multi-PAN
        assert (await guess_firmware_type(hass, path)) == FirmwareGuess(
            is_running=True, firmware_type=ApplicationType.CPC, source="multiprotocol"
        )
