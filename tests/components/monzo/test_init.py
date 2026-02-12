"""Tests for component initialisation."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from monzopy import AuthorisationExpiredError

from homeassistant.components.monzo.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_api_can_trigger_reauth(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reauth an existing profile reauthenticates the config entry."""
    await setup_integration(hass, polling_config_entry)

    monzo.user_account.accounts.side_effect = AuthorisationExpiredError()
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == SOURCE_REAUTH


async def test_migrate_entry_minor_version_1_2(hass: HomeAssistant) -> None:
    """Test migrating a 1.1 config entry to 1.2."""
    with patch("homeassistant.components.monzo.async_setup_entry", return_value=True):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "auth_implementation": DOMAIN,
                "token": {
                    "refresh_token": "mock-refresh-token",
                    "access_token": "mock-access-token",
                    "type": "Bearer",
                    "expires_in": 60,
                    "user_id": "600",
                },
            },
            version=1,
            minor_version=1,
            unique_id=600,
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.version == 1
        assert entry.minor_version == 2
        assert entry.unique_id == "600"
