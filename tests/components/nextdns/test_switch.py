"""Test switch of NextDNS integration."""

from datetime import timedelta
from unittest.mock import Mock, patch

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

from . import init_integration, mock_nextdns

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the switches."""
    with patch("homeassistant.components.nextdns.PLATFORMS", [Platform.SWITCH]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_on(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the switch can be turned on."""
    await init_integration(hass, mock_config_entry)

    state = hass.states.get("switch.fake_profile_block_page")
    assert state
    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.nextdns.NextDns.set_setting", return_value=True
    ) as mock_switch_on:
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

        mock_switch_on.assert_called_once()


async def test_switch_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the switch can be turned on."""
    await init_integration(hass, mock_config_entry)

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state == STATE_ON

    with patch(
        "homeassistant.components.nextdns.NextDns.set_setting", return_value=True
    ) as mock_switch_on:
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

        mock_switch_on.assert_called_once()


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

    freezer.tick(timedelta(minutes=10))
    with patch(
        "homeassistant.components.nextdns.NextDns.get_settings",
        side_effect=exc,
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    freezer.tick(timedelta(minutes=10))
    with mock_nextdns():
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

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
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, exc: Exception
) -> None:
    """Tests that the turn on/off service throws HomeAssistantError."""
    await init_integration(hass, mock_config_entry)

    with (
        patch("homeassistant.components.nextdns.NextDns.set_setting", side_effect=exc),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.fake_profile_block_page"},
            blocking=True,
        )


async def test_switch_auth_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Tests that the turn on/off action starts re-auth flow."""
    await init_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.nextdns.NextDns.set_setting",
        side_effect=InvalidApiKeyError,
    ):
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
