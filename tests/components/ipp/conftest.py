"""Fixtures for IPP integration tests."""
from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

from pyipp import Printer
import pytest

from homeassistant.components.ipp.const import CONF_BASE_PATH, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_UUID,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="IPP Printer",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.31",
            CONF_PORT: 631,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_BASE_PATH: "/ipp/print",
            CONF_UUID: "cfe92100-67c4-11d4-a45f-f8d027761251",
        },
        unique_id="cfe92100-67c4-11d4-a45f-f8d027761251",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.ipp.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def mock_printer(
    request: pytest.FixtureRequest,
) -> Printer:
    """Return the mocked printer."""
    fixture: str = "ipp/printer.json"
    if hasattr(request, "param") and request.param:
        fixture = request.param

    return Printer.from_dict(json.loads(load_fixture(fixture)))


@pytest.fixture
def mock_ipp_config_flow(
    mock_printer: Printer,
) -> Generator[None, MagicMock, None]:
    """Return a mocked IPP client."""

    with patch(
        "homeassistant.components.ipp.config_flow.IPP", autospec=True
    ) as ipp_mock:
        client = ipp_mock.return_value
        client.printer.return_value = mock_printer
        yield client


@pytest.fixture
def mock_ipp(
    request: pytest.FixtureRequest, mock_printer: Printer
) -> Generator[None, MagicMock, None]:
    """Return a mocked IPP client."""

    with patch(
        "homeassistant.components.ipp.coordinator.IPP", autospec=True
    ) as ipp_mock:
        client = ipp_mock.return_value
        client.printer.return_value = mock_printer
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_ipp: MagicMock
) -> MockConfigEntry:
    """Set up the IPP integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
