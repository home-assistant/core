"""Test button of NextDNS integration."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import init_integration


async def test_button(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test states of the button."""
    with patch("homeassistant.components.nextdns.PLATFORMS", [Platform.BUTTON]):
        entry = await init_integration(hass)

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_button_press(hass: HomeAssistant) -> None:
    """Test button press."""
    await init_integration(hass)

    now = dt_util.utcnow()
    with (
        patch("homeassistant.components.nextdns.NextDns.clear_logs") as mock_clear_logs,
        patch("homeassistant.core.dt_util.utcnow", return_value=now),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: "button.fake_profile_clear_logs"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_clear_logs.assert_called_once()

    state = hass.states.get("button.fake_profile_clear_logs")
    assert state
    assert state.state == now.isoformat()
