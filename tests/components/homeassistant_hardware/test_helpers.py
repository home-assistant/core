"""Test hardware helpers."""

from collections.abc import Callable
import logging
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest

from homeassistant.components.homeassistant_hardware.const import DATA_COMPONENT
from homeassistant.components.homeassistant_hardware.helpers import (
    async_firmware_update_context,
    async_is_firmware_update_in_progress,
    async_notify_firmware_info,
    async_register_firmware_info_callback,
    async_register_firmware_info_provider,
    async_register_firmware_update_in_progress,
    async_unregister_firmware_update_in_progress,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
)
from homeassistant.components.usb import USBDevice
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
    async_register_firmware_info_provider(hass, "zha", provider1_firmware)

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
    async_register_firmware_info_provider(hass, "otbr", provider2_firmware)

    # Double registration won't work
    with pytest.raises(ValueError, match="Domain zha is already registered"):
        async_register_firmware_info_provider(hass, "zha", provider1_firmware)

    # We can iterate over the results
    info = [i async for i in hass.data[DATA_COMPONENT].iter_firmware_info()]
    assert info == [
        FIRMWARE_INFO_EZSP,
        FIRMWARE_INFO_SPINEL,
    ]

    callback1 = Mock()
    cancel1 = async_register_firmware_info_callback(
        hass, "/dev/serial/by-id/device1", callback1
    )

    callback2 = Mock()
    cancel2 = async_register_firmware_info_callback(
        hass, "/dev/serial/by-id/device2", callback2
    )

    # And receive notification callbacks
    await async_notify_firmware_info(hass, "zha", firmware_info=FIRMWARE_INFO_EZSP)
    await async_notify_firmware_info(hass, "otbr", firmware_info=FIRMWARE_INFO_SPINEL)
    await async_notify_firmware_info(hass, "zha", firmware_info=FIRMWARE_INFO_EZSP)
    cancel1()
    await async_notify_firmware_info(hass, "zha", firmware_info=FIRMWARE_INFO_EZSP)
    await async_notify_firmware_info(hass, "otbr", firmware_info=FIRMWARE_INFO_SPINEL)
    cancel2()

    assert callback1.mock_calls == [
        call(FIRMWARE_INFO_EZSP),
        call(FIRMWARE_INFO_EZSP),
    ]

    assert callback2.mock_calls == [
        call(FIRMWARE_INFO_SPINEL),
        call(FIRMWARE_INFO_SPINEL),
    ]


async def test_dispatcher_iter_error_handling(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test HardwareInfoDispatcher ignoring errors from firmware info providers."""

    await async_setup_component(hass, "homeassistant_hardware", {})

    provider1_config_entry = MockConfigEntry(
        domain="zha",
        unique_id="some_unique_id1",
        data={},
    )
    provider1_config_entry.add_to_hass(hass)
    provider1_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    provider1_firmware = MagicMock(spec=["get_firmware_info"])
    provider1_firmware.get_firmware_info = MagicMock(side_effect=Exception("Boom!"))
    async_register_firmware_info_provider(hass, "zha", provider1_firmware)

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
    async_register_firmware_info_provider(hass, "otbr", provider2_firmware)

    with caplog.at_level(logging.ERROR):
        info = [i async for i in hass.data[DATA_COMPONENT].iter_firmware_info()]

    assert info == [FIRMWARE_INFO_SPINEL]
    assert "Error while getting firmware info from" in caplog.text


async def test_dispatcher_callback_error_handling(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test HardwareInfoDispatcher ignoring errors from firmware info callbacks."""

    await async_setup_component(hass, "homeassistant_hardware", {})
    provider1_config_entry = MockConfigEntry(
        domain="zha",
        unique_id="some_unique_id1",
        data={},
    )
    provider1_config_entry.add_to_hass(hass)
    provider1_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    provider1_firmware = MagicMock(spec=["get_firmware_info"])
    provider1_firmware.get_firmware_info = MagicMock(return_value=FIRMWARE_INFO_EZSP)
    async_register_firmware_info_provider(hass, "zha", provider1_firmware)

    callback1 = Mock(side_effect=Exception("Some error"))
    async_register_firmware_info_callback(hass, "/dev/serial/by-id/device1", callback1)

    callback2 = Mock()
    async_register_firmware_info_callback(hass, "/dev/serial/by-id/device1", callback2)

    with caplog.at_level(logging.ERROR):
        await async_notify_firmware_info(hass, "zha", firmware_info=FIRMWARE_INFO_EZSP)

    assert "Error while notifying firmware info listener" in caplog.text

    assert callback1.mock_calls == [call(FIRMWARE_INFO_EZSP)]
    assert callback2.mock_calls == [call(FIRMWARE_INFO_EZSP)]


async def test_firmware_update_tracking(hass: HomeAssistant) -> None:
    """Test firmware update tracking API."""
    await async_setup_component(hass, "homeassistant_hardware", {})

    device_path = "/dev/ttyUSB0"

    assert not async_is_firmware_update_in_progress(hass, device_path)

    # Register an update in progress
    async_register_firmware_update_in_progress(hass, device_path, "zha")
    assert async_is_firmware_update_in_progress(hass, device_path)

    with pytest.raises(ValueError, match="Firmware update already in progress"):
        async_register_firmware_update_in_progress(hass, device_path, "skyconnect")

    assert async_is_firmware_update_in_progress(hass, device_path)

    # Unregister the update with correct domain
    async_unregister_firmware_update_in_progress(hass, device_path, "zha")
    assert not async_is_firmware_update_in_progress(hass, device_path)

    # Test unregistering with wrong domain should raise an error
    async_register_firmware_update_in_progress(hass, device_path, "zha")
    with pytest.raises(ValueError, match="is owned by zha, not skyconnect"):
        async_unregister_firmware_update_in_progress(hass, device_path, "skyconnect")

    # Still registered to zha
    assert async_is_firmware_update_in_progress(hass, device_path)
    async_unregister_firmware_update_in_progress(hass, device_path, "zha")
    assert not async_is_firmware_update_in_progress(hass, device_path)


async def test_firmware_update_context_manager(hass: HomeAssistant) -> None:
    """Test firmware update progress context manager."""
    await async_setup_component(hass, "homeassistant_hardware", {})

    device_path = "/dev/ttyUSB0"

    # Initially no updates in progress
    assert not async_is_firmware_update_in_progress(hass, device_path)

    # Test successful completion
    async with async_firmware_update_context(hass, device_path, "zha"):
        assert async_is_firmware_update_in_progress(hass, device_path)

    # Should be cleaned up after context
    assert not async_is_firmware_update_in_progress(hass, device_path)

    # Test exception handling
    with pytest.raises(ValueError, match="test error"):  # noqa: PT012
        async with async_firmware_update_context(hass, device_path, "zha"):
            assert async_is_firmware_update_in_progress(hass, device_path)
            raise ValueError("test error")

    # Should still be cleaned up after exception
    assert not async_is_firmware_update_in_progress(hass, device_path)

    # Test concurrent context manager attempts should fail
    async with async_firmware_update_context(hass, device_path, "zha"):
        assert async_is_firmware_update_in_progress(hass, device_path)

        # Second context manager should fail to register
        with pytest.raises(ValueError, match="Firmware update already in progress"):
            async with async_firmware_update_context(hass, device_path, "skyconnect"):
                pytest.fail("We should not enter this context manager")

    # Should be cleaned up after first context
    assert not async_is_firmware_update_in_progress(hass, device_path)


async def test_dispatcher_callback_self_unregister(hass: HomeAssistant) -> None:
    """Test callbacks can unregister themselves during notification."""
    await async_setup_component(hass, "homeassistant_hardware", {})

    called_callbacks = []
    unregister_funcs = {}

    def create_self_unregistering_callback(name: str) -> Callable[[FirmwareInfo], None]:
        def callback(firmware_info: FirmwareInfo) -> None:
            called_callbacks.append(name)
            unregister_funcs[name]()

        return callback

    callback1 = create_self_unregistering_callback("callback1")
    callback2 = create_self_unregistering_callback("callback2")
    callback3 = create_self_unregistering_callback("callback3")

    # Register all three callbacks and store their unregister functions
    unregister_funcs["callback1"] = async_register_firmware_info_callback(
        hass, "/dev/serial/by-id/device1", callback1
    )
    unregister_funcs["callback2"] = async_register_firmware_info_callback(
        hass, "/dev/serial/by-id/device1", callback2
    )
    unregister_funcs["callback3"] = async_register_firmware_info_callback(
        hass, "/dev/serial/by-id/device1", callback3
    )

    # All callbacks should be called and unregister themselves
    await async_notify_firmware_info(hass, "zha", firmware_info=FIRMWARE_INFO_EZSP)
    assert set(called_callbacks) == {"callback1", "callback2", "callback3"}

    # No callbacks should be called since they all unregistered
    called_callbacks.clear()
    await async_notify_firmware_info(hass, "zha", firmware_info=FIRMWARE_INFO_EZSP)
    assert not called_callbacks


async def test_firmware_callback_no_usb_device(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test firmware notification when usb_device_from_path returns None."""
    await async_setup_component(hass, "homeassistant_hardware", {})
    await async_setup_component(hass, "usb", {})

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.helpers.usb_device_from_path",
            return_value=None,
        ),
        caplog.at_level(logging.DEBUG),
    ):
        await async_notify_firmware_info(
            hass,
            "zha",
            FirmwareInfo(
                device="/dev/ttyUSB99",
                firmware_type=ApplicationType.EZSP,
                firmware_version="7.4.4.0",
                owners=[],
                source="zha",
            ),
        )
        await hass.async_block_till_done()

    # This isn't a codepath that's expected but we won't fail in this case, just log
    assert "Cannot find USB for path /dev/ttyUSB99" in caplog.text


async def test_firmware_callback_no_hardware_domain(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test firmware notification when no hardware domain is found for device."""
    await async_setup_component(hass, "homeassistant_hardware", {})
    await async_setup_component(hass, "usb", {})

    # Create a USB device that doesn't match any hardware integration
    usb_device = USBDevice(
        device="/dev/ttyUSB0",
        vid="9999",
        pid="9999",
        serial_number="TEST123",
        manufacturer="Test Manufacturer",
        description="Test Device",
    )

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.helpers.usb_device_from_path",
            return_value=usb_device,
        ),
        caplog.at_level(logging.DEBUG),
    ):
        await async_notify_firmware_info(
            hass,
            "zha",
            FirmwareInfo(
                device="/dev/ttyUSB0",
                firmware_type=ApplicationType.EZSP,
                firmware_version="7.4.4.0",
                owners=[],
                source="zha",
            ),
        )
        await hass.async_block_till_done()

    assert "No hardware integration found for device" in caplog.text
