"""The tests for Netatmo siren."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.siren import (
    DOMAIN as SIREN_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_WEBHOOK_ID,
    Platform,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import (
    FAKE_WEBHOOK_ACTIVATION,
    selected_platforms,
    simulate_webhook,
    snapshot_platform_entities,
)

from tests.common import MockConfigEntry

NOC_ENTITY_ID = "siren.front"
NOC_MODULE_ID = "12:34:56:10:b9:0e"
NOC_HOME_ID = "91763b24c43d3e344f424e8b"


async def test_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test siren entity is created for NOC camera."""
    await snapshot_platform_entities(
        hass,
        config_entry,
        Platform.SIREN,
        entity_registry,
        snapshot,
    )


async def test_siren_turn_on_success(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test turning on siren succeeds when web_auth is configured."""
    with selected_platforms(["siren"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)
    await hass.async_block_till_done()

    mock_web_auth = MagicMock()
    mock_web_auth.async_siren_on = AsyncMock(return_value=True)
    config_entry.runtime_data.web_auth = mock_web_auth

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: NOC_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_web_auth.async_siren_on.assert_called_once_with(NOC_HOME_ID, NOC_MODULE_ID)
    assert hass.states.get(NOC_ENTITY_ID).state == STATE_ON


async def test_siren_turn_off_success(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test turning off siren succeeds when web_auth is configured."""
    with selected_platforms(["siren"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)
    await hass.async_block_till_done()

    mock_web_auth = MagicMock()
    mock_web_auth.async_siren_off = AsyncMock(return_value=True)
    config_entry.runtime_data.web_auth = mock_web_auth

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: NOC_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_web_auth.async_siren_off.assert_called_once_with(NOC_HOME_ID, NOC_MODULE_ID)
    assert hass.states.get(NOC_ENTITY_ID).state == STATE_OFF


async def test_siren_turn_on_no_credentials(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test turning on siren raises HomeAssistantError when web_auth is not configured."""
    with selected_platforms(["siren"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)
    await hass.async_block_till_done()

    config_entry.runtime_data.web_auth = None

    with pytest.raises(HomeAssistantError, match="Siren credentials not configured"):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: NOC_ENTITY_ID},
            blocking=True,
        )


async def test_siren_turn_on_command_fails(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test turning on siren raises HomeAssistantError when the API command fails."""
    with selected_platforms(["siren"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)
    await hass.async_block_till_done()

    mock_web_auth = MagicMock()
    mock_web_auth.async_siren_on = AsyncMock(return_value=False)
    config_entry.runtime_data.web_auth = mock_web_auth

    with pytest.raises(HomeAssistantError, match="Siren command failed"):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: NOC_ENTITY_ID},
            blocking=True,
        )


async def test_siren_availability_based_on_alim_status(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test siren availability is based on alim_status, not webhook status.

    The entity must be available as soon as the camera is powered (alim_status
    is set), regardless of whether the webhook has been established.
    """
    with selected_platforms(["siren"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Without webhook activation, entity should still be available
    # because alim_status is populated from the initial homestatus poll.
    state = hass.states.get(NOC_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_siren_state_from_callback(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test siren state is correctly updated from async_update_callback."""
    with selected_platforms(["siren"]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)
    await hass.async_block_till_done()

    # Default state from fixture (siren_status = "no_sound")
    state = hass.states.get(NOC_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
