"""Test the Threema Gateway notify platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from threema.gateway import GatewayError
from threema.gateway.exception import GatewayServerError

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.threema.const import (
    CONF_API_SECRET,
    CONF_GATEWAY_ID,
    CONF_RECIPIENT,
    DOMAIN,
    SUBENTRY_TYPE_RECIPIENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MOCK_API_SECRET,
    MOCK_GATEWAY_ID,
    MOCK_RECIPIENT_ID,
    MOCK_SUBENTRY_ID,
)

from tests.common import MockConfigEntry

RECIPIENT_SUBENTRY = {
    "data": {CONF_RECIPIENT: MOCK_RECIPIENT_ID},
    "subentry_id": MOCK_SUBENTRY_ID,
    "subentry_type": SUBENTRY_TYPE_RECIPIENT,
    "title": MOCK_RECIPIENT_ID,
    "unique_id": MOCK_RECIPIENT_ID,
}


@pytest.fixture
def mock_subentries():
    """Override: provide a recipient subentry for notify tests."""
    return [RECIPIENT_SUBENTRY]


async def test_notify_entity_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: tuple[MagicMock, MagicMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test notify entity is created from subentry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 1
    assert notify_entities[0].unique_id == f"{MOCK_GATEWAY_ID}_{MOCK_RECIPIENT_ID}"


async def test_notify_entity_not_created_without_subentry(
    hass: HomeAssistant,
    mock_connection: MagicMock,
    mock_send: tuple[MagicMock, MagicMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no notify entity without subentries."""
    entry = MockConfigEntry(
        title=f"Threema {MOCK_GATEWAY_ID}",
        domain=DOMAIN,
        data={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
        },
        unique_id=MOCK_GATEWAY_ID,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 0


async def test_send_message_simple(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: tuple[MagicMock, MagicMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sending a message via notify entity (simple mode)."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 1

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "send_message",
        {"entity_id": notify_entities[0].entity_id, "message": "Hello from tests!"},
        blocking=True,
    )

    mock_send[1].assert_called_once()
    call_kwargs = mock_send[1].call_args[1]
    assert call_kwargs["to_id"] == MOCK_RECIPIENT_ID
    assert call_kwargs["text"] == "Hello from tests!"
    mock_send[1].return_value.send.assert_awaited_once()


async def test_send_message_e2e(
    hass: HomeAssistant,
    mock_config_entry_with_keys: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: tuple[MagicMock, MagicMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sending a message via notify entity (E2E mode)."""
    entry = MockConfigEntry(
        title=f"Threema {MOCK_GATEWAY_ID}",
        domain=DOMAIN,
        data=mock_config_entry_with_keys.data,
        unique_id=MOCK_GATEWAY_ID,
        subentries_data=[RECIPIENT_SUBENTRY],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 1

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "send_message",
        {"entity_id": notify_entities[0].entity_id, "message": "Hello E2E!"},
        blocking=True,
    )

    mock_send[0].assert_called_once()
    call_kwargs = mock_send[0].call_args[1]
    assert call_kwargs["to_id"] == MOCK_RECIPIENT_ID
    assert call_kwargs["text"] == "Hello E2E!"
    mock_send[0].return_value.send.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "match"),
    [
        (GatewayServerError(status=401), "Error sending message"),
        (GatewayError("Network error"), "Error sending message"),
        (GatewayServerError(status=500), "Error sending message"),
    ],
    ids=["auth_error", "send_error", "server_error_non_auth"],
)
async def test_send_message_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: tuple[MagicMock, MagicMock],
    entity_registry: er.EntityRegistry,
    side_effect: Exception,
    match: str,
) -> None:
    """Test notify entity handles send errors."""
    mock_send[1].return_value.send.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "send_message",
            {
                "entity_id": notify_entities[0].entity_id,
                "message": "Hello!",
            },
            blocking=True,
        )
