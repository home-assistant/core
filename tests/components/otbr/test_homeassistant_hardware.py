"""Test Home Assistant Hardware platform for OTBR."""

from unittest.mock import AsyncMock, Mock, call, patch

import pytest
import voluptuous as vol

from homeassistant.components.homeassistant_hardware.helpers import (
    register_firmware_info_callback,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningAddon,
    OwningIntegration,
)
from homeassistant.components.otbr.homeassistant_hardware import async_get_firmware_info
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from . import TEST_COPROCESSOR_VERSION

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_get_firmware_info(hass: HomeAssistant) -> None:
    """Test `async_get_firmware_info`."""

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
    otbr.runtime_data.get_coprocessor_version.return_value = TEST_COPROCESSOR_VERSION

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
        fw_info = await async_get_firmware_info(hass, otbr)

    assert fw_info == FirmwareInfo(
        device="/dev/ttyUSB1",
        firmware_type=ApplicationType.SPINEL,
        firmware_version=TEST_COPROCESSOR_VERSION,
        source="otbr",
        owners=[
            OwningIntegration(config_entry_id=otbr.entry_id),
            OwningAddon(slug="openthread_border_router"),
        ],
    )


async def test_get_firmware_info_ignored(hass: HomeAssistant) -> None:
    """Test `async_get_firmware_info` with ignored entry."""

    otbr = MockConfigEntry(
        domain="otbr",
        unique_id="some_unique_id",
        data={},
        version=1,
        minor_version=2,
    )
    otbr.add_to_hass(hass)

    fw_info = await async_get_firmware_info(hass, otbr)
    assert fw_info is None


async def test_get_firmware_info_bad_addon(hass: HomeAssistant) -> None:
    """Test `async_get_firmware_info`."""

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
    otbr.runtime_data.get_coprocessor_version.return_value = TEST_COPROCESSOR_VERSION

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
        fw_info = await async_get_firmware_info(hass, otbr)

    assert fw_info == FirmwareInfo(
        device="/dev/ttyUSB1",
        firmware_type=ApplicationType.SPINEL,
        firmware_version=TEST_COPROCESSOR_VERSION,
        source="otbr",
        owners=[
            OwningIntegration(config_entry_id=otbr.entry_id),
        ],
    )


async def test_get_firmware_info_no_coprocessor_version(hass: HomeAssistant) -> None:
    """Test `async_get_firmware_info`."""

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
        fw_info = await async_get_firmware_info(hass, otbr)

    assert fw_info == FirmwareInfo(
        device="/dev/ttyUSB1",
        firmware_type=ApplicationType.SPINEL,
        firmware_version=None,
        source="otbr",
        owners=[
            OwningIntegration(config_entry_id=otbr.entry_id),
        ],
    )


@pytest.mark.parametrize(
    ("version", "expected_version"),
    [
        (TEST_COPROCESSOR_VERSION, TEST_COPROCESSOR_VERSION),
        (HomeAssistantError(), None),
    ],
)
async def test_hardware_firmware_info_provider_notification(
    hass: HomeAssistant,
    version: str | Exception,
    expected_version: str | None,
    get_active_dataset_tlvs: AsyncMock,
    get_border_agent_id: AsyncMock,
    get_extended_address: AsyncMock,
    get_coprocessor_version: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the OTBR provides hardware and firmware information."""
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

    await async_setup_component(hass, "homeassistant_hardware", {})

    callback = Mock()
    register_firmware_info_callback(hass, "/dev/ttyUSB1", callback)

    with (
        patch(
            "homeassistant.components.otbr.homeassistant_hardware.is_hassio",
            return_value=True,
        ),
    ):
        get_coprocessor_version.side_effect = version
        await hass.config_entries.async_setup(otbr.entry_id)

    assert callback.mock_calls == [
        call(
            FirmwareInfo(
                device="/dev/ttyUSB1",
                firmware_type=ApplicationType.SPINEL,
                firmware_version=expected_version,
                source="otbr",
                owners=[
                    OwningIntegration(config_entry_id=otbr.entry_id),
                    OwningAddon(slug="openthread_border_router"),
                ],
            )
        )
    ]
