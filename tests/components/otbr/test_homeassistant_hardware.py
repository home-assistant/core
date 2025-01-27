"""Test Home Assistant Hardware platform for OTBR."""

from unittest.mock import AsyncMock, patch

import voluptuous as vol

from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningAddon,
    OwningIntegration,
)
from homeassistant.components.otbr.homeassistant_hardware import get_firmware_info
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

COPROCESSOR_VERSION = "OPENTHREAD/thread-reference-20200818-1740-g33cc75ed3; NRF52840; Jun 2 2022 14:25:49"


async def test_get_firmware_info(hass: HomeAssistant) -> None:
    """Test `get_firmware_info`."""

    otbr = MockConfigEntry(
        domain="otbr",
        unique_id="some_unique_id",
        data={
            "device": "/dev/ttyUSB1",
            "url": "http://openthread_border_router:8888",
        },
        version=1,
        minor_version=2,
    )
    otbr.add_to_hass(hass)
    otbr.mock_state(hass, ConfigEntryState.LOADED)

    otbr.runtime_data = AsyncMock()
    otbr.runtime_data.get_coprocessor_version.return_value = COPROCESSOR_VERSION

    with (
        patch(
            "homeassistant.components.otbr.homeassistant_hardware.is_hassio",
            return_value=True,
        ),
        patch(
            "homeassistant.components.otbr.homeassistant_hardware.valid_addon",
            return_value=True,
        ),
    ):
        fw_info = await get_firmware_info(hass, otbr)

    assert fw_info == FirmwareInfo(
        device="/dev/ttyUSB1",
        firmware_type=ApplicationType.SPINEL,
        firmware_version=COPROCESSOR_VERSION,
        source="otbr",
        owners=[
            OwningIntegration(config_entry_id=otbr.entry_id),
            OwningAddon(slug="openthread_border_router"),
        ],
    )


async def test_get_firmware_info_ignored(hass: HomeAssistant) -> None:
    """Test `get_firmware_info` with ignored entry."""

    otbr = MockConfigEntry(
        domain="otbr",
        unique_id="some_unique_id",
        data={},
        version=1,
        minor_version=2,
    )
    otbr.add_to_hass(hass)

    fw_info = await get_firmware_info(hass, otbr)
    assert fw_info is None


async def test_get_firmware_info_bad_addon(hass: HomeAssistant) -> None:
    """Test `get_firmware_info`."""

    otbr = MockConfigEntry(
        domain="otbr",
        unique_id="some_unique_id",
        data={
            "device": "/dev/ttyUSB1",
            "url": "http://openthread_border_router:8888",
        },
        version=1,
        minor_version=2,
    )
    otbr.add_to_hass(hass)
    otbr.mock_state(hass, ConfigEntryState.LOADED)

    otbr.runtime_data = AsyncMock()
    otbr.runtime_data.get_coprocessor_version.return_value = COPROCESSOR_VERSION

    with (
        patch(
            "homeassistant.components.otbr.homeassistant_hardware.is_hassio",
            return_value=True,
        ),
        patch(
            "homeassistant.components.otbr.homeassistant_hardware.valid_addon",
            side_effect=vol.Invalid("Bad addon name"),
        ),
    ):
        fw_info = await get_firmware_info(hass, otbr)

    assert fw_info == FirmwareInfo(
        device="/dev/ttyUSB1",
        firmware_type=ApplicationType.SPINEL,
        firmware_version=COPROCESSOR_VERSION,
        source="otbr",
        owners=[
            OwningIntegration(config_entry_id=otbr.entry_id),
        ],
    )


async def test_get_firmware_info_no_coprocessor_version(hass: HomeAssistant) -> None:
    """Test `get_firmware_info`."""

    otbr = MockConfigEntry(
        domain="otbr",
        unique_id="some_unique_id",
        data={
            "device": "/dev/ttyUSB1",
            "url": "http://openthread_border_router:8888",
        },
        version=1,
        minor_version=2,
    )
    otbr.add_to_hass(hass)
    otbr.mock_state(hass, ConfigEntryState.LOADED)

    otbr.runtime_data = AsyncMock()
    otbr.runtime_data.get_coprocessor_version.side_effect = HomeAssistantError()

    with (
        patch(
            "homeassistant.components.otbr.homeassistant_hardware.is_hassio",
            return_value=False,
        ),
    ):
        fw_info = await get_firmware_info(hass, otbr)

    assert fw_info == FirmwareInfo(
        device="/dev/ttyUSB1",
        firmware_type=ApplicationType.SPINEL,
        firmware_version=None,
        source="otbr",
        owners=[
            OwningIntegration(config_entry_id=otbr.entry_id),
        ],
    )
