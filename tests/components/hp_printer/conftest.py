"""Common fixtures for the HP Printer tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

from aiohpprinter import (
    HpConsumable,
    HpCopyUsage,
    HpFaxUsage,
    HpPrinterData,
    HpPrinterDevice,
    HpPrinterStatus,
    HpPrinterUsage,
    HpScannerUsage,
)
import pytest

from homeassistant.components.hp_printer.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

HOST = "192.168.1.12"
SERIAL_NUMBER = "TH12A3B4CD"
TITLE = "HP OfficeJet Pro 9020 series"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hp_printer.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_device() -> HpPrinterDevice:
    """Return the identity of a mocked HP OfficeJet Pro 9022e."""
    return HpPrinterDevice(
        make_and_model=TITLE,
        make_and_model_family=TITLE,
        sku_identifier="9022e",
        serial_number=SERIAL_NUMBER,
        product_number="226Y0B",
        manufacturer_name="HP",
        manufactured_at=datetime(2023, 3, 13),
    )


def _ink(
    consumable_id: str,
    marker_color: str,
    station: str,
    level: float,
    pages_remaining: int | None = None,
) -> HpConsumable:
    """Return an ink cartridge as reported by an HP OfficeJet Pro 9022e."""
    return HpConsumable(
        consumable_id=consumable_id,
        consumable_type="ink",
        marker_color=marker_color,
        state="used",
        brand="HP",
        station=station,
        percentage_level_remaining=level,
        estimated_pages_remaining=pages_remaining,
    )


@pytest.fixture
def mock_data(mock_device: HpPrinterDevice) -> HpPrinterData:
    """Return data captured from a real HP OfficeJet Pro 9022e.

    That printer reports no pages-remaining estimates, so the black cartridge
    gets the one an HP Color LaserJet M255dw reports for its black toner.
    """
    return HpPrinterData(
        online=True,
        device=mock_device,
        status=HpPrinterStatus(device_status="inpowersave"),
        consumables=[
            _ink("C", "Cyan", "1", 40.0),
            HpConsumable(
                consumable_id="CMYK",
                consumable_type="printhead",
                state="ok",
                brand="HP",
                station="0",
            ),
            _ink("K", "Black", "4", 80.0, pages_remaining=550),
            _ink("M", "Magenta", "2", 40.0),
            _ink("Y", "Yellow", "3", 40.0),
        ],
        printer_usage=HpPrinterUsage(
            total_impressions=875,
            monochrome_impressions=226,
            color_impressions=649,
            simplex_sheets=697,
            duplex_sheets=83,
            jam_events=2,
            mispick_events=24,
        ),
        scanner_usage=HpScannerUsage(
            scan_images=4279,
            adf_images=2947,
            duplex_sheets=589,
            flatbed_images=1310,
            jam_events=11,
            mispick_events=6,
        ),
        copy_usage=HpCopyUsage(
            total_impressions=20,
            adf_images=9,
            flatbed_images=5,
            monochrome_impressions=2,
            color_impressions=18,
        ),
        fax_usage=HpFaxUsage(total_impressions=0),
    )


@pytest.fixture
def mock_hp_printer(
    mock_device: HpPrinterDevice, mock_data: HpPrinterData
) -> Generator[AsyncMock]:
    """Mock the aiohpprinter client used by the coordinator and the config flow."""
    with (
        patch(
            "homeassistant.components.hp_printer.coordinator.HpPrinter", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.hp_printer.config_flow.HpPrinter",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.base_url = f"http://{HOST}:80"
        client.device.return_value = mock_device
        client.update.return_value = mock_data
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        data={CONF_HOST: HOST},
        unique_id=SERIAL_NUMBER,
    )
