"""Fixtures for EnOcean integration tests."""

from collections.abc import Generator
from typing import Final
from unittest.mock import Mock, patch

from enocean_async.protocol.erp1.telegram import ERP1Telegram
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.enocean.const import DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from . import TelegramReceiver

ENTRY_CONFIG: Final[dict[str, str]] = {
    CONF_DEVICE: "/dev/ttyUSB0",
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="device_chip_id",
        data=ENTRY_CONFIG,
    )


@pytest.fixture
def mock_gateway() -> Generator[Mock]:
    """Return a mocked EnOcean gateway."""
    with patch(
        "homeassistant.components.enocean.Gateway", autospec=True
    ) as gateway_class:
        yield gateway_class.return_value


@pytest.fixture
def receive_telegram(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_gateway: Mock
) -> TelegramReceiver:
    """Add the config entry and return a function simulating a received telegram.

    As on startup, the entry is set up together with the first EnOcean platform.
    """
    mock_config_entry.add_to_hass(hass)

    async def _receive(telegram: ERP1Telegram) -> None:
        mock_gateway.add_erp1_received_callback.call_args.args[0](telegram)
        await hass.async_block_till_done()

    return _receive
