"""Test button of NextDNS integration."""

from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError, InvalidApiKeyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.nextdns.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
) -> None:
    """Test states of the button."""
    with patch("homeassistant.components.nextdns.PLATFORMS", [Platform.BUTTON]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2023-10-21")
async def test_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
) -> None:
    """Test button press."""
    await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.fake_profile_clear_logs"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_nextdns_client.clear_logs.assert_called_once()

    state = hass.states.get("button.fake_profile_clear_logs")
    assert state
    assert state.state == "2023-10-21T00:00:00+00:00"


@pytest.mark.parametrize(
    "exc",
    [
        ApiError(Mock()),
        TimeoutError,
        ClientConnectorError(Mock(), Mock()),
        ClientError,
    ],
)
async def test_button_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
    exc: Exception,
) -> None:
    """Tests that the press action throws HomeAssistantError."""
    await init_integration(hass, mock_config_entry)

    mock_nextdns_client.clear_logs.side_effect = exc

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while calling the NextDNS API method for button.fake_profile_clear_logs",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.fake_profile_clear_logs"},
            blocking=True,
        )


async def test_button_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
) -> None:
    """Tests that the press action starts re-auth flow."""
    await init_integration(hass, mock_config_entry)

    mock_nextdns_client.clear_logs.side_effect = InvalidApiKeyError

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.fake_profile_clear_logs"},
        blocking=True,
    )

    assert mock_config_entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id
