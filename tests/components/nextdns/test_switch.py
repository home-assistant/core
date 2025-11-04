"""Test switch of NextDNS integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory
from nextdns import ApiError, InvalidApiKeyError
import pytest
from syrupy.assertion import SnapshotAssertion
from tenacity import RetryError

from homeassistant.components.nextdns.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test states of the switches."""
    with patch("homeassistant.components.nextdns.PLATFORMS", [Platform.SWITCH]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test the switch can be turned on."""
    await init_integration(hass, mock_config_entry)

    state = hass.states.get("switch.fake_profile_block_page")
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.fake_profile_block_page"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.fake_profile_block_page")
    assert state
    assert state.state == STATE_ON

    mock_nextdns_client.set_setting.assert_called_once()


async def test_switch_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test the switch can be turned on."""
    await init_integration(hass, mock_config_entry)

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.fake_profile_web3"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state == STATE_OFF

    mock_nextdns_client.set_setting.assert_called_once()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "exc",
    [
        ApiError("API Error"),
        RetryError("Retry Error"),
        TimeoutError,
    ],
)
async def test_availability(
    hass: HomeAssistant,
    exc: Exception,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    with patch("homeassistant.components.nextdns.PLATFORMS", [Platform.SWITCH]):
        await init_integration(hass, mock_config_entry)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    entity_ids = (entry.entity_id for entry in entity_entries)

    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    mock_nextdns_client.set_setting.side_effect = exc

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_nextdns_client.set_setting.side_effect = None

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "exc",
    [
        ApiError(Mock()),
        TimeoutError,
        ClientConnectorError(Mock(), Mock()),
        ClientError,
    ],
)
async def test_switch_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
    exc: Exception,
) -> None:
    """Tests that the turn on/off service throws HomeAssistantError."""
    await init_integration(hass, mock_config_entry)

    mock_nextdns_client.set_setting.side_effect = exc

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.fake_profile_block_page"},
            blocking=True,
        )


async def test_switch_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Tests that the turn on/off action starts re-auth flow."""
    await init_integration(hass, mock_config_entry)

    mock_nextdns_client.set_setting.side_effect = InvalidApiKeyError

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.fake_profile_block_page"},
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
