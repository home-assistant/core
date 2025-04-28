"""Tests for component initialisation."""

from datetime import timedelta
from unittest.mock import AsyncMock

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
