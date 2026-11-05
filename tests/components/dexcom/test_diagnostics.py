"""Tests for the Dexcom diagnostics."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pydexcom.errors import SessionError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.dexcom.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import CONFIG, init_integration


@pytest.mark.freeze_time("2025-04-19T17:03:33+00:00")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics show the latest reading and redact the account."""
    entry = await init_integration(hass)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == snapshot(exclude=props("created_at", "entry_id", "modified_at"))


async def test_entry_diagnostics_no_reading(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the diagnostics when Dexcom has no current reading."""
    entry = await init_integration(hass)

    with patch(
        "homeassistant.components.dexcom.Dexcom.get_current_glucose_reading",
        return_value=None,
    ):
        freezer.tick(timedelta(minutes=3))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["last_update_success"] is True
    assert result["reading"] is None


async def test_entry_diagnostics_setup_failed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the diagnostics still work when the entry failed to set up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_username",
        unique_id="test_username",
        data=CONFIG,
    )
    with patch(
        "homeassistant.components.dexcom.Dexcom",
        side_effect=SessionError,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["config_entry"]["data"]["password"] == "**REDACTED**"
    assert result["last_update_success"] is None
    assert result["reading"] is None
