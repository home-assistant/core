"""Common fixtures for the Teleinfo tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.teleinfo.const import CONF_SERIAL_PORT, DOMAIN
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from tests.common import MockConfigEntry

USB_DISCOVERY_INFO = UsbServiceInfo(
    device="/dev/ttyUSB0",
    pid="6015",
    vid="0403",
    serial_number="AB1234",
    manufacturer="FTDI",
    description="FT230X Basic UART",
)

# Common labels shared by all contract types (monophase)
_COMMON_LABELS: dict[str, str] = {
    "ADCO": "021861348497",
    "OPTARIF": "",  # overridden per contract
    "ISOUSC": "30",
    "PTEC": "",  # overridden per contract
    "IINST": "012",
    "IMAX": "090",
    "PAPP": "02830",
    "HHPHC": "A",
    "MOTDETAT": "000000",
}

MOCK_DECODED_DATA_BASE: dict[str, str] = {
    **_COMMON_LABELS,
    "OPTARIF": "BASE",
    "PTEC": "TH..",
    "BASE": "045367891",
}

MOCK_DECODED_DATA_HC: dict[str, str] = {
    **_COMMON_LABELS,
    "OPTARIF": "HC..",
    "PTEC": "HC..",
    "HCHC": "025643781",
    "HCHP": "031285904",
}

MOCK_DECODED_DATA_EJP: dict[str, str] = {
    **_COMMON_LABELS,
    "OPTARIF": "EJP.",
    "PTEC": "HN..",
    "EJPHN": "038912456",
    "EJPHPM": "007654321",
    "PEJP": "30",
}

MOCK_DECODED_DATA_TEMPO: dict[str, str] = {
    **_COMMON_LABELS,
    "OPTARIF": "BBR(",
    "PTEC": "HCJB",
    "BBRHCJB": "018328702",
    "BBRHPJB": "023739545",
    "BBRHCJW": "001466099",
    "BBRHPJW": "002132883",
    "BBRHCJR": "000860118",
    "BBRHPJR": "000844115",
    "DEMAIN": "ROUG",
}

# Default mock data (Tempo) — used by most existing tests
MOCK_DECODED_DATA = MOCK_DECODED_DATA_TEMPO

MOCK_FRAME = b"\x02\nADCO 021861348497 L\r\x03"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Teleinfo (/dev/ttyUSB0)",
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
        unique_id="021861348497",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.teleinfo.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_teleinfo() -> Generator[MagicMock]:
    """Mock the teleinfo (pyteleinfo) library decode function."""
    mock = MagicMock()
    mock.decode = MagicMock(return_value=MOCK_DECODED_DATA)
    mock.TeleinfoError = type("TeleinfoError", (Exception,), {})

    with (
        patch(
            "homeassistant.components.teleinfo.coordinator.decode",
            mock.decode,
        ),
        patch(
            "homeassistant.components.teleinfo.config_flow.decode",
            mock.decode,
        ),
    ):
        yield mock


@pytest.fixture
def mock_serial_port() -> Generator[MagicMock]:
    """Mock read_frame to return a frame without real serial I/O."""
    with (
        patch(
            "homeassistant.components.teleinfo.coordinator.read_frame",
            return_value=MOCK_FRAME,
        ) as mock_read,
        patch(
            "homeassistant.components.teleinfo.config_flow.read_frame",
            new=mock_read,
        ),
    ):
        yield mock_read
