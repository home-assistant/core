"""Test button of NextDNS integration."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import init_integration

from tests.common import snapshot_platform


async def test_button(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test states of the button."""
    with patch("homeassistant.components.nextdns.PLATFORMS", [Platform.BUTTON]):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


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
