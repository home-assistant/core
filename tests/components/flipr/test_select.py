"""Test the Flipr select for Hub."""

import logging
from unittest.mock import AsyncMock

from flipr_api.exceptions import FliprError

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

SELECT_ENTITY_ID = "select.flipr_hub_myhubid_mode"


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test the creation and values of the Flipr select."""

    mock_flipr_client.search_all_ids.return_value = {"flipr": [], "hub": ["myhubid"]}

    await setup_integration(hass, mock_config_entry)

    # Check entity unique_id value that is generated in FliprEntity base class.
    entity = entity_registry.async_get(SELECT_ENTITY_ID)
    _LOGGER.debug("Found entity = %s", entity)
    assert entity.unique_id == "myhubid-hubMode"

    mode = hass.states.get(SELECT_ENTITY_ID)
    _LOGGER.debug("Found mode = %s", mode)
    assert mode
    assert mode.state == "planning"
    assert mode.attributes.get(ATTR_OPTIONS) == ["auto", "manual", "planning"]


async def test_select_actions(
    hass: HomeAssistant,
    mock_flipr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the actions on the Flipr Hub select."""

    mock_flipr_client.search_all_ids.return_value = {"flipr": [], "hub": ["myhubid"]}

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SELECT_ENTITY_ID)
    assert state.state == "planning"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: "manual"},
        blocking=True,
    )
    state = hass.states.get(SELECT_ENTITY_ID)
    assert state.state == "manual"


async def test_no_select_found(
    hass: HomeAssistant,
    mock_flipr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the select absence."""

    mock_flipr_client.search_all_ids.return_value = {"flipr": [], "hub": []}

    await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_entity_ids(SELECT_ENTITY_ID)


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
    entity = entity_registry.async_get(SELECT_ENTITY_ID)
    assert entity is None
