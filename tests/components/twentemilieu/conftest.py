"""Fixtures for the Twente Milieu integration tests."""
from __future__ import annotations

from collections.abc import Generator
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from twentemilieu import WasteType

from homeassistant.components.twentemilieu.const import (
    CONF_HOUSE_LETTER,
    CONF_HOUSE_NUMBER,
    CONF_POST_CODE,
    DOMAIN,
)
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={
            CONF_ID: 12345,
            CONF_POST_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_HOUSE_LETTER: "A",
        },
        unique_id="12345",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.twentemilieu.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_twentemilieu_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked Twente Milieu client."""
    with patch(
        "homeassistant.components.twentemilieu.config_flow.TwenteMilieu", autospec=True
    ) as twentemilieu_mock:
        twentemilieu = twentemilieu_mock.return_value
        twentemilieu.unique_id.return_value = 12345
        yield twentemilieu


@pytest.fixture
def mock_twentemilieu() -> Generator[None, MagicMock, None]:
    """Return a mocked Twente Milieu client."""
    with patch(
        "homeassistant.components.twentemilieu.TwenteMilieu", autospec=True
    ) as twentemilieu_mock:
        twentemilieu = twentemilieu_mock.return_value
        twentemilieu.unique_id.return_value = 12345
        twentemilieu.update.return_value = {
            WasteType.NON_RECYCLABLE: [date(2021, 11, 1), date(2021, 12, 1)],
            WasteType.ORGANIC: [date(2021, 11, 2)],
            WasteType.PACKAGES: [date(2021, 11, 3)],
            WasteType.PAPER: [],
            WasteType.TREE: [date(2022, 1, 6)],
        }
        yield twentemilieu


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twentemilieu: MagicMock,
) -> MockConfigEntry:
    """Set up the TwenteMilieu integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
