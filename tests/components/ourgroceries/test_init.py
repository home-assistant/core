"""Unit tests for the OurGroceries integration."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.ourgroceries import ClientError, InvalidLoginException
from homeassistant.components.ourgroceries.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant,
    setup_integration: None,
    ourgroceries_config_entry: MockConfigEntry | None,
) -> None:
    """Test loading and unloading of the config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert ourgroceries_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(ourgroceries_config_entry.entry_id)
    assert ourgroceries_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.fixture
def login_with_error(exception, ourgroceries: AsyncMock):
    """Fixture to simulate error on login."""
    ourgroceries.login.side_effect = (exception,)


@pytest.mark.parametrize(
    ("exception", "status"),
    [
        (InvalidLoginException, ConfigEntryState.SETUP_ERROR),
        (ClientError, ConfigEntryState.SETUP_RETRY),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_init_failure(
    hass: HomeAssistant,
    login_with_error,
    setup_integration: None,
    status: ConfigEntryState,
    ourgroceries_config_entry: MockConfigEntry | None,
) -> None:
    """Test an initialization error on integration load."""
    assert ourgroceries_config_entry.state == status
