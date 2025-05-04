"""Test button of NextDNS integration."""

from unittest.mock import Mock, patch

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError, InvalidApiKeyError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.nextdns.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.fake_profile_clear_logs"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_clear_logs.assert_called_once()

    state = hass.states.get("button.fake_profile_clear_logs")
    assert state
    assert state.state == now.isoformat()


@pytest.mark.parametrize(
    "exc",
    [
        ApiError(Mock()),
        TimeoutError,
        ClientConnectorError(Mock(), Mock()),
        ClientError,
    ],
)
async def test_button_failure(hass: HomeAssistant, exc: Exception) -> None:
    """Tests that the press action throws HomeAssistantError."""
    await init_integration(hass)

    with (
        patch("homeassistant.components.nextdns.NextDns.clear_logs", side_effect=exc),
        pytest.raises(
            HomeAssistantError,
            match="An error occurred while calling the NextDNS API method for button.fake_profile_clear_logs",
        ),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.fake_profile_clear_logs"},
            blocking=True,
        )


async def test_button_auth_error(hass: HomeAssistant) -> None:
    """Tests that the press action starts re-auth flow."""
    entry = await init_integration(hass)

    with patch(
        "homeassistant.components.nextdns.NextDns.clear_logs",
        side_effect=InvalidApiKeyError,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.fake_profile_clear_logs"},
            blocking=True,
        )

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
