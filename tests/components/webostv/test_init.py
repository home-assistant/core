"""The tests for the LG webOS TV platform."""

from unittest.mock import Mock

from aiowebostv import WebOsTvPairError
import pytest

from homeassistant.components.webostv.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant

from . import setup_webostv


async def test_reauth_setup_entry(
    hass: HomeAssistant, client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test reauth flow triggered by setup entry."""
    monkeypatch.setattr(client, "is_connected", Mock(return_value=False))
    monkeypatch.setattr(client, "connect", Mock(side_effect=WebOsTvPairError))
    entry = await setup_webostv(hass)

    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_key_update_setup_entry(
    hass: HomeAssistant, client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test key update from setup entry."""
    monkeypatch.setattr(client, "client_key", "new_key")
    entry = await setup_webostv(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_CLIENT_SECRET] == "new_key"
