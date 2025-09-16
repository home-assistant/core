"""Test actions of Bring! integration."""

from unittest.mock import AsyncMock

from bring_api import (
    ActivityType,
    BringActivityResponse,
    BringNotificationType,
    BringRequestException,
    ReactionType,
)
import pytest

from homeassistant.components.bring.const import (
    ATTR_REACTION,
    DOMAIN,
    SERVICE_ACTIVITY_STREAM_REACTION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("reaction", "call_arg"),
    [
        ("drooling", ReactionType.DROOLING),
        ("heart", ReactionType.HEART),
        ("monocle", ReactionType.MONOCLE),
        ("thumbs_up", ReactionType.THUMBS_UP),
    ],
)
async def test_send_reaction(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
    reaction: str,
    call_arg: ReactionType,
) -> None:
    """Test send activity stream reaction."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ACTIVITY_STREAM_REACTION,
        service_data={
            ATTR_ENTITY_ID: "event.einkauf_activities",
            ATTR_REACTION: reaction,
        },
        blocking=True,
    )

    mock_bring_client.notify.assert_called_once_with(
        "e542eef6-dba7-4c31-a52c-29e6ab9d83a5",
        BringNotificationType.LIST_ACTIVITY_STREAM_REACTION,
        receiver="9a21fdfc-63a4-441a-afc1-ef3030605a9d",
        activity="673594a9-f92d-4cb6-adf1-d2f7a83207a4",
        activity_type=ActivityType.LIST_ITEMS_CHANGED,
        reaction=call_arg,
    )


async def test_send_reaction_exception(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
) -> None:
    """Test send activity stream reaction with exception."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED
    mock_bring_client.notify.side_effect = BringRequestException
    with pytest.raises(
        HomeAssistantError,
        match="Failed to send reaction for Bring! due to a connection error, try again later",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVITY_STREAM_REACTION,
            service_data={
                ATTR_ENTITY_ID: "event.einkauf_activities",
                ATTR_REACTION: "heart",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_bring_client")
async def test_send_reaction_config_entry_not_loaded(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Test send activity stream reaction config entry not loaded exception."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(bring_config_entry.entry_id)

    assert bring_config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(
        ServiceValidationError,
        match="The account associated with this Bring! list is either not loaded or disabled in Home Assistant",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVITY_STREAM_REACTION,
            service_data={
                ATTR_ENTITY_ID: "event.einkauf_activities",
                ATTR_REACTION: "heart",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_bring_client")
async def test_send_reaction_unknown_entity(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test send activity stream reaction unknown entity exception."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    entity_registry.async_update_entity(
        "event.einkauf_activities", disabled_by=er.RegistryEntryDisabler.USER
    )
    with pytest.raises(
        ServiceValidationError,
        match="Failed to send reaction for Bring! — Unknown entity event.einkauf_activities",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVITY_STREAM_REACTION,
            service_data={
                ATTR_ENTITY_ID: "event.einkauf_activities",
                ATTR_REACTION: "heart",
            },
            blocking=True,
        )


async def test_send_reaction_not_found(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
) -> None:
    """Test send activity stream reaction not found validation error."""
    mock_bring_client.get_activity.return_value = BringActivityResponse.from_dict(
        {"timeline": [], "timestamp": "2025-01-01T03:09:33.036Z", "totalEvents": 0}
    )

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(
        HomeAssistantError,
        match="Failed to send reaction for Bring! — No recent activity found",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVITY_STREAM_REACTION,
            service_data={
                ATTR_ENTITY_ID: "event.einkauf_activities",
                ATTR_REACTION: "heart",
            },
            blocking=True,
        )
