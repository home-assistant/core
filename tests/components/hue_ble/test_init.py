"""Test hue_ble setup process."""

from unittest.mock import patch

from bleak.backends.device import BLEDevice
import pytest

from homeassistant.components.hue_ble.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import TEST_DEVICE_MAC, TEST_DEVICE_NAME

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device


@pytest.mark.parametrize(
    (
        "ble_device",
        "scanner_count",
        "connect_result",
        "poll_state_result",
        "message",
    ),
    [
        (
            None,
            2,
            True,
            True,
            "The light was not found.",
        ),
        (
            None,
            0,
            True,
            True,
            "No Bluetooth scanners are available to search for the light.",
        ),
        (
            generate_ble_device(TEST_DEVICE_MAC, TEST_DEVICE_NAME),
            2,
            False,
            True,
            "Device found but unable to connect.",
        ),
        (
            generate_ble_device(TEST_DEVICE_MAC, TEST_DEVICE_NAME),
            2,
            True,
            False,
            "Device found but unable to connect.",
        ),
    ],
    ids=["no_device", "no_scanners", "error_connect", "error_poll"],
)
async def test_setup_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    ble_device: BLEDevice | None,
    scanner_count: int,
    connect_result: bool,
    poll_state_result: bool,
    message: str,
) -> None:
    """Test that ConfigEntryNotReady is raised if there is an error condition."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="abcd", data={})
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.hue_ble.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.hue_ble.async_scanner_count",
            return_value=scanner_count,
        ),
        patch(
            "homeassistant.components.hue_ble.HueBleLight.connect",
            return_value=connect_result,
        ),
        patch(
            "homeassistant.components.hue_ble.HueBleLight.poll_state",
            return_value=poll_state_result,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert message in caplog.text


async def test_setup(
    hass: HomeAssistant,
) -> None:
    """Test that the config is loaded if there are no errors."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="abcd", data={})
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.hue_ble.async_ble_device_from_address",
            return_value=generate_ble_device(TEST_DEVICE_MAC, TEST_DEVICE_NAME),
        ),
        patch(
            "homeassistant.components.hue_ble.async_scanner_count",
            return_value=1,
        ),
        patch(
            "homeassistant.components.hue_ble.HueBleLight.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hue_ble.HueBleLight.poll_state",
            return_value=True,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
