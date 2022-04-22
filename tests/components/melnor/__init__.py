"""Tests for the melnor integration."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from melnor_bluetooth.device import Device

from homeassistant.components.melnor.const import DOMAIN
from homeassistant.const import CONF_MAC
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

FAKE_MAC = "ABCABCABCABC"
FAKE_MODEL = "12345"
FAKE_NAME = "4 Valve Timer"
FAKE_NUM_VALVES = 4
FAKE_SENSOR_EXISTS = False

FAKE_DEVICE = Device(mac=FAKE_MAC)

FAKE_DEVICE_2 = Device(mac="ABCABCABCADB")

TEST_CONNECTION = {CONF_MAC: FAKE_MAC}


async def setup_integration(
    hass: HomeAssistantType,
) -> MockConfigEntry:
    """Mock ConfigEntry in Home Assistant."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_MAC,
        data={CONF_MAC: FAKE_MAC},
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


def _mocked_device(device: Device) -> Device:
    device = MagicMock(auto_spec=Device, name=FAKE_NAME)

    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.is_connected = Mock(return_value=True)
    device.mac = Mock(return_value=FAKE_MAC)
    device.name = Mock(return_value=FAKE_NAME)
    device.valve_count = Mock(return_value=FAKE_NUM_VALVES)

    return device


def _patch_scanner(
    devices: list[Device] = [],
):  # pylint: disable=dangerous-default-value
    @contextmanager
    def _patcher():
        def fake_scanner(callback, scan_timeout_seconds):

            if devices.__len__() > 0:
                for device in devices:
                    callback(device.mac)

        with patch(
            "homeassistant.components.melnor.discovery.scanner",
            side_effect=fake_scanner,
        ):
            yield

    return _patcher()


def _patch_device(fake_device: Device | None = None):
    @contextmanager
    def _patcher():
        if fake_device is not None:
            device = _mocked_device(fake_device)
        else:
            device = _mocked_device(FAKE_DEVICE)

        with patch(
            "homeassistant.components.melnor.Device", return_value=device
        ), patch(
            "homeassistant.components.melnor.config_flow.Device",
            return_value=device,
        ):
            yield

    return _patcher()
