"""Test hardware helpers."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from homeassistant.components.homeassistant_hardware.const import DATA_COMPONENT
from homeassistant.components.homeassistant_hardware.helpers import (
    notify_firmware_info,
    register_firmware_info_provider,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

FIRMWARE_INFO_EZSP = FirmwareInfo(
    device="/dev/serial/by-id/device1",
    firmware_type=ApplicationType.EZSP,
    firmware_version=None,
    source="zha",
    owners=[AsyncMock(is_running=AsyncMock(return_value=True))],
)

FIRMWARE_INFO_SPINEL = FirmwareInfo(
    device="/dev/serial/by-id/device2",
    firmware_type=ApplicationType.SPINEL,
    firmware_version=None,
    source="otbr",
    owners=[AsyncMock(is_running=AsyncMock(return_value=True))],
)


async def test_dispatcher_registration(hass: HomeAssistant) -> None:
    """Test HardwareInfoDispatcher registration."""

    await async_setup_component(hass, "homeassistant_hardware", {})

    # Mock provider 1 with a synchronous method to pull firmware info
    provider1_config_entry = MockConfigEntry(
        domain="zha",
        unique_id="some_unique_id1",
        data={},
    )
    provider1_config_entry.add_to_hass(hass)
    provider1_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    provider1_firmware = MagicMock(spec=["get_firmware_info"])
    provider1_firmware.get_firmware_info = MagicMock(return_value=FIRMWARE_INFO_EZSP)
    register_firmware_info_provider(hass, "zha", provider1_firmware)

    # Mock provider 2 with an asynchronous method to pull firmware info
    provider2_config_entry = MockConfigEntry(
        domain="otbr",
        unique_id="some_unique_id2",
        data={},
    )
    provider2_config_entry.add_to_hass(hass)
    provider2_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    provider2_firmware = MagicMock(spec=["async_get_firmware_info"])
    provider2_firmware.async_get_firmware_info = AsyncMock(
        return_value=FIRMWARE_INFO_SPINEL
    )
    register_firmware_info_provider(hass, "otbr", provider2_firmware)

    # Double registration won't work
    with pytest.raises(ValueError, match="Domain zha is already registered"):
        register_firmware_info_provider(hass, "zha", provider1_firmware)

    # We can iterate over the results
    info = [i async for i in hass.data[DATA_COMPONENT].iter_firmware_info()]
    assert info == [
        FIRMWARE_INFO_EZSP,
        FIRMWARE_INFO_SPINEL,
    ]

    # And receive notifications
    with patch.object(
        hass.data[DATA_COMPONENT],
        "notify_firmware_info",
        AsyncMock(wraps=hass.data[DATA_COMPONENT].notify_firmware_info),
    ) as notify_listener:
        await notify_firmware_info(hass, "zha", firmware_info=FIRMWARE_INFO_SPINEL)
        await notify_firmware_info(hass, "zha", firmware_info=FIRMWARE_INFO_EZSP)
        await notify_firmware_info(hass, "otbr", firmware_info=FIRMWARE_INFO_SPINEL)

    assert notify_listener.mock_calls == [
        call("zha", FIRMWARE_INFO_SPINEL),
        call("zha", FIRMWARE_INFO_EZSP),
        call("otbr", FIRMWARE_INFO_SPINEL),
    ]
