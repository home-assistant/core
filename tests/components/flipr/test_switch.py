"""Test the Flipr switch for Hub."""

from unittest.mock import AsyncMock

from flipr_api.exceptions import FliprError

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import MOCK_HUB_STATE_OFF

from tests.common import MockConfigEntry

SWITCH_ENTITY_ID = "switch.flipr_hub_myhubid"


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test the creation and values of the Flipr switch."""

    mock_flipr_client.search_all_ids.return_value = {"flipr": [], "hub": ["myhubid"]}

    await setup_integration(hass, mock_config_entry)

    # Check entity unique_id value that is generated in FliprEntity base class.
    entity = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert entity.unique_id == "myhubid-hubState"

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state
    assert state.state == STATE_ON


async def test_switch_actions(
    hass: HomeAssistant,
    mock_flipr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the actions on the Flipr Hub switch."""

    mock_flipr_client.search_all_ids.return_value = {"flipr": [], "hub": ["myhubid"]}

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state.state == STATE_ON

    mock_flipr_client.set_hub_state.return_value = MOCK_HUB_STATE_OFF
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state.state == STATE_OFF


async def test_no_switch_found(
    hass: HomeAssistant,
    mock_flipr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the switch absence."""

    mock_flipr_client.search_all_ids.return_value = {"flipr": [], "hub": []}

    await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_entity_ids(SWITCH_DOMAIN)


async def test_error_flipr_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test the Flipr sensors error."""

    mock_flipr_client.search_all_ids.return_value = {"flipr": [], "hub": ["myhubid"]}

    mock_flipr_client.get_hub_state.side_effect = FliprError(
        "Error during flipr data retrieval..."
    )

    await setup_integration(hass, mock_config_entry)

    # Check entity is not generated because of the FliprError raised.
    entity = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert entity is None
