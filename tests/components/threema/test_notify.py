"""Test the Threema Gateway notify platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from threema.gateway.exception import GatewayServerError

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.threema.const import (
    CONF_RECIPIENT,
    SUBENTRY_TYPE_RECIPIENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_GATEWAY_ID, MOCK_RECIPIENT_ID, MOCK_SUBENTRY_ID

from tests.common import MockConfigEntry, MockConfigEntrySubentry


async def test_notify_entity_created(
    hass: HomeAssistant,
    mock_config_entry_with_subentry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test notify entity is created from subentry."""
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry_with_subentry.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 1
    assert notify_entities[0].unique_id == f"{MOCK_GATEWAY_ID}_{MOCK_SUBENTRY_ID}"


async def test_notify_entity_not_created_without_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test no notify entity without subentries."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 0


async def test_send_message_simple(
    hass: HomeAssistant,
    mock_config_entry_with_subentry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test sending a message via notify entity (simple mode)."""
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry_with_subentry.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 1

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "send_message",
        {"entity_id": notify_entities[0].entity_id, "message": "Hello from tests!"},
        blocking=True,
    )

    mock_send.simple.assert_called_once()


async def test_send_message_e2e(
    hass: HomeAssistant,
    mock_config_entry_with_keys: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test sending a message via notify entity (E2E mode)."""
    entry = MockConfigEntry(
        title=f"Threema {MOCK_GATEWAY_ID}",
        domain="threema",
        data=mock_config_entry_with_keys.data,
        unique_id=MOCK_GATEWAY_ID,
        subentries_data=[
            MockConfigEntrySubentry(
                data={CONF_RECIPIENT: MOCK_RECIPIENT_ID},
                subentry_id=MOCK_SUBENTRY_ID,
                subentry_type=SUBENTRY_TYPE_RECIPIENT,
                title=MOCK_RECIPIENT_ID,
                unique_id=MOCK_RECIPIENT_ID,
            ),
        ],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 1

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "send_message",
        {"entity_id": notify_entities[0].entity_id, "message": "Hello E2E!"},
        blocking=True,
    )

    mock_send.e2e.assert_called_once()


async def test_send_message_auth_error(
    hass: HomeAssistant,
    mock_config_entry_with_subentry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test notify entity handles auth failure during send."""
    mock_config_entry_with_subentry.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.client.SimpleTextMessage", autospec=True
    ) as simple_mock:
        simple_instance = MagicMock()
        simple_instance.send = AsyncMock(side_effect=GatewayServerError(status=401))
        simple_mock.return_value = simple_instance

        await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry_with_subentry.entry_id
        )
        notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                NOTIFY_DOMAIN,
                "send_message",
                {
                    "entity_id": notify_entities[0].entity_id,
                    "message": "Hello!",
                },
                blocking=True,
            )


async def test_send_message_send_error(
    hass: HomeAssistant,
    mock_config_entry_with_subentry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test notify entity handles send failure."""
    mock_config_entry_with_subentry.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.client.SimpleTextMessage", autospec=True
    ) as simple_mock:
        simple_instance = MagicMock()
        simple_instance.send = AsyncMock(side_effect=Exception("Network error"))
        simple_mock.return_value = simple_instance

        await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry_with_subentry.entry_id
        )
        notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                NOTIFY_DOMAIN,
                "send_message",
                {
                    "entity_id": notify_entities[0].entity_id,
                    "message": "Hello!",
                },
                blocking=True,
            )
