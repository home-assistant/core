"""Test helpers for Tibber."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.tibber.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Tibber config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: "token"},
        unique_id="tibber",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
async def mock_tibber_setup(
    config_entry: MockConfigEntry, hass: HomeAssistant
) -> AsyncGenerator[None, MagicMock]:
    """Mock tibber entry setup."""
    unique_user_id = "unique_user_id"
    title = "title"

    tibber_mock = MagicMock()
    tibber_mock.update_info = AsyncMock(return_value=True)
    tibber_mock.user_id = PropertyMock(return_value=unique_user_id)
    tibber_mock.name = PropertyMock(return_value=title)
    tibber_mock.send_notification = AsyncMock()
    tibber_mock.rt_disconnect = AsyncMock()

    with patch("tibber.Tibber", return_value=tibber_mock):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield tibber_mock
