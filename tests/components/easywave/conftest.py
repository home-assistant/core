"""Pytest configuration and fixtures for Easywave Core tests."""

import asyncio
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.easywave.const import (
    BUCKET_SUBENTRY_TITLES,
    CONF_BUTTON_COUNT,
    CONF_DEVICE_PATH,
    CONF_DEVICE_TITLE,
    CONF_ENTRY_TYPE,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_SENSOR_CAPABILITIES,
    CONF_SENSOR_SERIAL,
    CONF_SWITCH_MODE,
    CONF_TRANSMITTER_SERIAL,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
    ENTRY_TYPE_NEO_SENSOR,
    ENTRY_TYPE_TRANSMITTER,
    SUBENTRY_TYPE_EASYWAVE_NEO_SENSOR,
    SUBENTRY_TYPE_EASYWAVE_TRANSMITTER,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
    bucket_subentry_unique_id,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from tests.common import MockConfigEntry

MOCK_ENTRY_DATA = {
    CONF_DEVICE_PATH: "/dev/ttyACM0",
    CONF_USB_VID: 0x155A,
    CONF_USB_PID: 0x1014,
    CONF_USB_SERIAL_NUMBER: "12345",
    CONF_USB_MANUFACTURER: "ELDAT",
    CONF_USB_PRODUCT: "RX11 USB Transceiver",
}

MOCK_ENTRY_ID = "easywave_test_entry_id"
MOCK_GATEWAY_TITLE = MOCK_ENTRY_DATA[CONF_USB_PRODUCT]
MOCK_TRANSMITTER_SERIAL = "aa" * 16
MOCK_TRANSMITTER_DEVICE_ID = f"transmitter_{MOCK_TRANSMITTER_SERIAL}"
MOCK_NEO_SENSOR_SERIAL = "bb" * 16
MOCK_NEO_SENSOR_DEVICE_ID = f"neo_sensor_{MOCK_NEO_SENSOR_SERIAL}"


def _bucket_subentry_data(
    *,
    subentry_type: str,
    devices: dict[str, dict[str, Any]],
) -> ConfigSubentryData:
    """Return a device-type bucket subentry for config entry tests."""
    return ConfigSubentryData(
        data={CONF_DEVICES: devices},
        subentry_type=subentry_type,
        title=BUCKET_SUBENTRY_TITLES[subentry_type],
        unique_id=bucket_subentry_unique_id(MOCK_ENTRY_ID, subentry_type),
    )


def _transmitter_device_record(
    *,
    title: str = "Test Transmitter",
    serial: str = MOCK_TRANSMITTER_SERIAL,
    button_count: int = 4,
    switch_mode: str | None = None,
    grouping_mode: str | None = None,
) -> ConfigSubentryData:
    """Return a transmitter bucket subentry for config entry tests."""
    device_id = f"transmitter_{serial}"
    return _bucket_subentry_data(
        subentry_type=SUBENTRY_TYPE_EASYWAVE_TRANSMITTER,
        devices={
            device_id: {
                CONF_DEVICE_TITLE: title,
                CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
                CONF_TRANSMITTER_SERIAL: serial,
                CONF_OPERATING_TYPE: "1",
                CONF_BUTTON_COUNT: button_count,
                CONF_GROUPING_MODE: grouping_mode or TRANSMITTER_GROUPING_GROUP,
                CONF_SWITCH_MODE: switch_mode or TRANSMITTER_SWITCH_IMPULSE,
            }
        },
    )


def _neo_sensor_device_record(
    *,
    title: str = "Neo Sensor",
    serial: str = MOCK_NEO_SENSOR_SERIAL,
    capabilities: int = 0,
) -> ConfigSubentryData:
    """Return a neo sensor bucket subentry for config entry tests."""
    device_id = f"neo_sensor_{serial}"
    return _bucket_subentry_data(
        subentry_type=SUBENTRY_TYPE_EASYWAVE_NEO_SENSOR,
        devices={
            device_id: {
                CONF_DEVICE_TITLE: title,
                CONF_ENTRY_TYPE: ENTRY_TYPE_NEO_SENSOR,
                CONF_SENSOR_SERIAL: serial,
                CONF_SENSOR_CAPABILITIES: capabilities,
            }
        },
    )


def _entry_with_subentries(
    *records: ConfigSubentryData,
    **entry_kwargs: Any,
) -> MockConfigEntry:
    """Return a gateway config entry with optional device bucket subentries."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=MOCK_GATEWAY_TITLE,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        subentries_data=records,
        **entry_kwargs,
    )


async def async_terminate_listener_receive(timeout: float = 30.0) -> None:
    """Stop the coordinator listener loop instead of spinning on None."""
    raise asyncio.CancelledError


def mock_easywave_transceiver(*, connected: bool = True) -> MagicMock:
    """Return a connected transceiver mock with library-boundary defaults."""
    transceiver = MagicMock()
    transceiver.is_connected = connected
    transceiver.device_path = "/dev/ttyACM0" if connected else None
    transceiver.usb_serial_number = "12345"
    transceiver.hw_version = "1.0"
    transceiver.fw_version = "2.0"
    transceiver.connect = AsyncMock(return_value=connected)
    transceiver.reconnect = AsyncMock(return_value=connected)
    transceiver.disconnect = AsyncMock()
    transceiver.dispose = AsyncMock()
    transceiver.set_disconnect_callback = MagicMock()
    transceiver.set_connected_callback = MagicMock()
    transceiver.cancel_pending_receives = AsyncMock()
    transceiver.receive_telegram = AsyncMock(
        side_effect=async_terminate_listener_receive
    )
    return transceiver


async def async_stop_easywave_listener(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Cancel any coordinator telegram listener started during setup."""
    if entry.runtime_data is None:
        return
    await entry.runtime_data.coordinator.suspend_telegram_listener()
    await hass.async_block_till_done()


async def async_setup_easywave_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    transceiver: MagicMock | None = None,
    *,
    country: str | None = "DE",
) -> MagicMock:
    """Set up Easywave with a real coordinator and mocked hardware."""
    transceiver = transceiver or mock_easywave_transceiver()
    entry.add_to_hass(hass)
    if country is not None:
        hass.config.country = country
    with patch(
        "homeassistant.components.easywave.RX11Transceiver",
        return_value=transceiver,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    await async_stop_easywave_listener(hass, entry)
    return transceiver


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock gateway ConfigEntry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=MOCK_GATEWAY_TITLE,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
    )


@pytest.fixture
def mock_config_entry_with_transmitter() -> MockConfigEntry:
    """Return a gateway ConfigEntry with a transmitter device."""
    return _entry_with_subentries(_transmitter_device_record())


@pytest.fixture
def mock_config_entry_with_neo_sensor() -> MockConfigEntry:
    """Return a gateway ConfigEntry with a neo sensor device."""
    return _entry_with_subentries(_neo_sensor_device_record())


@pytest.fixture
def mock_usb_discovery_info() -> UsbServiceInfo:
    """Return a mock USB discovery info."""
    return UsbServiceInfo(
        device="/dev/ttyACM0",
        vid="155A",
        pid="1014",
        serial_number="12345",
        manufacturer="ELDAT",
        description="RX11 USB Transceiver",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.easywave.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
