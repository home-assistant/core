"""Tests for the Toon component."""

from unittest.mock import patch

from homeassistant.components.toon import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from tests.common import MockConfigEntry


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
            },
            "agreement_id": "test-agreement-id",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.toon.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_entry_minor_version_2_2(hass: HomeAssistant) -> None:
    """Test migrating a 2.1 config entry to 2.2."""
    with patch("homeassistant.components.toon.async_setup_entry", return_value=True):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "auth_implementation": DOMAIN,
                "token": {
                    "refresh_token": "mock-refresh-token",
                    "access_token": "mock-access-token",
                    "type": "Bearer",
                    "expires_in": 60,
                },
                "agreement_id": 123,
            },
            version=2,
            minor_version=1,
            unique_id=123,
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.version == 2
        assert entry.minor_version == 2
        assert entry.unique_id == "123"
