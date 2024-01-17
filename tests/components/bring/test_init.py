"""Unit tests for the bring integration."""
from unittest.mock import Mock

import pytest

from homeassistant.components.bring import (
    BringAuthException,
    BringParseException,
    BringRequestException,
)
from homeassistant.components.bring.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant,
    setup_integration: None,
    bring_config_entry: MockConfigEntry | None,
) -> None:
    """Test loading and unloading of the config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert bring_config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(bring_config_entry.entry_id)
    assert bring_config_entry.state == ConfigEntryState.NOT_LOADED


@pytest.fixture
def login_with_error(exception, bring: Mock):
    """Fixture to simulate error on login."""
    bring.login.side_effect = (exception,)


@pytest.mark.parametrize(
    ("exception", "status"),
    [
        (BringRequestException, ConfigEntryState.SETUP_RETRY),
        (BringAuthException, ConfigEntryState.SETUP_ERROR),
        (BringParseException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_init_failure(
    hass: HomeAssistant,
    login_with_error,
    setup_integration: None,
    status: ConfigEntryState,
    bring_config_entry: MockConfigEntry | None,
) -> None:
    """Test an initialization error on integration load."""
    assert bring_config_entry.state == status
