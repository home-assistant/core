"""Test hardware utilities."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    guess_firmware_info,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ZHA_CONFIG_ENTRY = MockConfigEntry(
    domain="zha",
    unique_id="some_unique_id",
    data={
        "device": {
            "path": "/dev/ttyUSB1",
            "baudrate": 115200,
            "flow_control": None,
        },
        "radio_type": "ezsp",
    },
    version=4,
)

ZHA_CONFIG_ENTRY2 = MockConfigEntry(
    domain="zha",
    unique_id="some_other_unique_id",
    data={
        "device": {
            "path": "/dev/ttyUSB2",
            "baudrate": 115200,
            "flow_control": None,
        },
        "radio_type": "ezsp",
    },
    version=4,
)


async def test_guess_firmware_info_unknown(hass: HomeAssistant) -> None:
    """Test guessing the firmware type."""

    assert (await guess_firmware_info(hass, "/dev/missing")) == FirmwareInfo(
        device="/dev/missing",
        firmware_type=ApplicationType.EZSP,
        firmware_version=None,
        source="unknown",
        owners=[],
    )


async def test_guess_firmware_info_integrations(hass: HomeAssistant) -> None:
    """Test guessing the firmware via OTBR and ZHA."""

    # One instance of ZHA and two OTBRs
    zha = MockConfigEntry(domain="zha", unique_id="some_unique_id_1")
    zha.add_to_hass(hass)

    otbr1 = MockConfigEntry(domain="otbr", unique_id="some_unique_id_2")
    otbr1.add_to_hass(hass)

    otbr2 = MockConfigEntry(domain="otbr", unique_id="some_unique_id_3")
    otbr2.add_to_hass(hass)

    # First ZHA is running with the stick
    zha_firmware_info = FirmwareInfo(
        device="/dev/serial/by-id/device1",
        firmware_type=ApplicationType.EZSP,
        firmware_version=None,
        source="zha",
        owners=[AsyncMock(is_running=AsyncMock(return_value=True))],
    )

    # First OTBR: neither the addon or the integration are loaded
    otbr_firmware_info1 = FirmwareInfo(
        device="/dev/serial/by-id/device1",
        firmware_type=ApplicationType.SPINEL,
        firmware_version=None,
        source="otbr",
        owners=[
            AsyncMock(is_running=AsyncMock(return_value=False)),
            AsyncMock(is_running=AsyncMock(return_value=False)),
        ],
    )

    # Second OTBR: fully running but is with an unrelated device
    otbr_firmware_info2 = FirmwareInfo(
        device="/dev/serial/by-id/device2",  # An unrelated device
        firmware_type=ApplicationType.SPINEL,
        firmware_version=None,
        source="otbr",
        owners=[
            AsyncMock(is_running=AsyncMock(return_value=True)),
            AsyncMock(is_running=AsyncMock(return_value=True)),
        ],
    )

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.util.get_zha_firmware_info",
            return_value=zha_firmware_info,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.get_otbr_firmware_info",
            side_effect=lambda _, config_entry: {
                otbr1: otbr_firmware_info1,
                otbr2: otbr_firmware_info2,
            }[config_entry],
        ),
    ):
        # ZHA wins for the first stick, since it's actually running
        assert (
            await guess_firmware_info(hass, "/dev/serial/by-id/device1")
        ) == zha_firmware_info

        # Second stick is communicating exclusively with the second OTBR
        assert (
            await guess_firmware_info(hass, "/dev/serial/by-id/device2")
        ) == otbr_firmware_info2

        # If we stop ZHA, OTBR will take priority
        zha_firmware_info.owners[0].is_running.return_value = False
        otbr_firmware_info1.owners[0].is_running.return_value = True
        assert (
            await guess_firmware_info(hass, "/dev/serial/by-id/device1")
        ) == otbr_firmware_info1
