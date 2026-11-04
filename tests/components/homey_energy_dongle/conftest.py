"""Common fixtures for Homey Energy Dongle tests."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

from dsmr_parser import telegram_specifications
from dsmr_parser.objects import Telegram
from dsmr_parser.parsers import TelegramParser
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.homey_energy_dongle.const import (
    CONF_DSMR_VERSION,
    CONF_WS_PATH,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import EQUIPMENT_IDENTIFIER, TELEGRAM_V5

type TelegramQueue = asyncio.Queue[Telegram | str | Exception]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.homey_energy_dongle.async_setup_entry",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_onboarding() -> Generator[MagicMock]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=False,
    ) as mock_onboarding:
        yield mock_onboarding


@pytest.fixture
def telegram_data() -> str:
    """Return the raw telegram the dongle sends."""
    return TELEGRAM_V5


@pytest.fixture
def telegram(telegram_data: str) -> Telegram:
    """Return the parsed telegram."""
    parser = TelegramParser(telegram_specifications.V5, apply_checksum_validation=False)
    return parser.parse(telegram_data)


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Patch the dongle client class."""
    with patch(
        "homeassistant.components.homey_energy_dongle.coordinator.EnergyDongleClient",
        autospec=True,
    ) as client:
        client.return_value.__aenter__.return_value = client.return_value
        yield client


@pytest.fixture
def telegrams(mock_client: MagicMock) -> TelegramQueue:
    """Feed the dongle's telegram stream; an exception ends the stream."""
    queue: TelegramQueue = asyncio.Queue()

    async def stream_parsed(*, skip_parse_errors: bool) -> AsyncGenerator[Telegram]:
        while True:
            item = await queue.get()
            if isinstance(item, Exception):
                raise item
            if not isinstance(item, Telegram):
                raise TypeError("stream_parsed received a raw telegram")
            yield item

    async def stream_telegrams() -> AsyncGenerator[str]:
        while True:
            item = await queue.get()
            if isinstance(item, Exception):
                raise item
            if not isinstance(item, str):
                raise TypeError("stream_telegrams received a parsed telegram")
            yield item

    mock_client.return_value.stream_parsed.side_effect = stream_parsed
    mock_client.return_value.stream_telegrams.side_effect = stream_telegrams
    return queue


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Homey Energy Dongle config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Homey Energy Dongle",
        unique_id=EQUIPMENT_IDENTIFIER,
        data={
            CONF_HOST: "192.168.1.88",
            CONF_PORT: 80,
            CONF_WS_PATH: "/ws",
            CONF_DSMR_VERSION: "5",
        },
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    telegrams: TelegramQueue,
    telegram: Telegram,
) -> MockConfigEntry:
    """Set up the integration with one telegram in the stream."""
    telegrams.put_nowait(telegram)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
