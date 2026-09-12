"""Test the Threema Gateway notify platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.threema.client import (
    ThreemaAuthError,
    ThreemaConnectionError,
    ThreemaSendError,
)
from homeassistant.components.threema.const import SUBENTRY_TYPE_RECIPIENT
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_NAME, CONF_RECIPIENT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_GATEWAY_ID, MOCK_RECIPIENT_ID, RECIPIENT_SUBENTRY

from tests.common import MockConfigEntry

_OTHER_SUBENTRY: ConfigSubentryDataWithId = {
    "data": {},
    "subentry_id": "other_subentry_id",
    "subentry_type": "other",
    "title": "Other",
    "unique_id": None,
}

_SECOND_RECIPIENT_ID = "WXYZ9999"
_SECOND_RECIPIENT_SUBENTRY: ConfigSubentryDataWithId = {
    "data": {CONF_RECIPIENT: _SECOND_RECIPIENT_ID},
    "subentry_id": "second_recipient_subentry_id",
    "subentry_type": SUBENTRY_TYPE_RECIPIENT,
    "title": "Second recipient",
    "unique_id": _SECOND_RECIPIENT_ID,
}

_NAMED_RECIPIENT_SUBENTRY: ConfigSubentryDataWithId = {
    "data": {CONF_RECIPIENT: _SECOND_RECIPIENT_ID, CONF_NAME: "Dad"},
    "subentry_id": "named_recipient_subentry_id",
    "subentry_type": SUBENTRY_TYPE_RECIPIENT,
    "title": f"Dad ({_SECOND_RECIPIENT_ID})",
    "unique_id": _SECOND_RECIPIENT_ID,
}

# Simulates a subentry created before the display name was stored
# separately in `data` — only the title carries "Name (RECIPIENT_ID)".
_LEGACY_NAMED_RECIPIENT_SUBENTRY: ConfigSubentryDataWithId = {
    "data": {CONF_RECIPIENT: _SECOND_RECIPIENT_ID},
    "subentry_id": "legacy_named_recipient_subentry_id",
    "subentry_type": SUBENTRY_TYPE_RECIPIENT,
    "title": f"Mom ({_SECOND_RECIPIENT_ID})",
    "unique_id": _SECOND_RECIPIENT_ID,
}


async def test_notify_entity_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
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


@pytest.mark.parametrize("mock_subentries", [[RECIPIENT_SUBENTRY, _OTHER_SUBENTRY]])
async def test_notify_entity_skips_non_recipient_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test notify setup only creates entities for recipient subentries."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 1
    assert notify_entities[0].unique_id == f"{MOCK_GATEWAY_ID}_{MOCK_RECIPIENT_ID}"


@pytest.mark.parametrize(
    "mock_subentries", [[RECIPIENT_SUBENTRY, _SECOND_RECIPIENT_SUBENTRY]]
)
async def test_notify_entities_get_separate_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test each recipient gets its own device, not a shared one.

    A device can only belong to a single config subentry; sharing one
    across recipient subentries makes Home Assistant silently reassign
    it whenever a new recipient is added, orphaning the previous one.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 2

    device_ids = {e.device_id for e in notify_entities}
    assert len(device_ids) == 2
    for device_id in device_ids:
        assert device_id is not None
        device = device_registry.async_get(device_id)
        assert device is not None
        assert device.config_entries_subentries[mock_config_entry.entry_id] != {None}


@pytest.mark.parametrize("mock_subentries", [[_NAMED_RECIPIENT_SUBENTRY]])
async def test_notify_entity_id_includes_gateway_name_and_recipient_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test entity_id is threema_<gateway>_<name>_<recipient id>.

    The display name (device/friendly name) stays "Name (ID)" for
    disambiguation in the UI, but the entity_id is independently built
    from the gateway id, name and recipient id, so it stays stable and
    unique across multiple gateways even when recipients share a name.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 1
    assert notify_entities[0].entity_id == "notify.threema_testgwy_dad_wxyz9999"

    device = device_registry.async_get(notify_entities[0].device_id)
    assert device is not None
    assert device.name == "Dad (WXYZ9999)"


@pytest.mark.parametrize("mock_subentries", [[_LEGACY_NAMED_RECIPIENT_SUBENTRY]])
async def test_notify_entity_id_recovers_name_from_legacy_title(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the name is recovered from the title for older subentries.

    Subentries created before the display name was stored separately in
    `data` only carry it baked into the title ("Mom (WXYZ9999)"); both the
    entity_id and the device name should still reflect "Mom", not fall
    back to the raw ID alone.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 1
    assert notify_entities[0].entity_id == "notify.threema_testgwy_mom_wxyz9999"

    device = device_registry.async_get(notify_entities[0].device_id)
    assert device is not None
    assert device.name == "Mom (WXYZ9999)"


@pytest.mark.parametrize("mock_subentries", [[]])
async def test_notify_entity_not_created_without_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no notify entity without subentries."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 0


async def test_send_message_simple(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
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

    mock_send_message.assert_called_once_with(MOCK_RECIPIENT_ID, "Hello from tests!")


async def test_send_message_with_title(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a title is formatted as a leading bold line in the sent text."""
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
        {
            "entity_id": notify_entities[0].entity_id,
            "message": "Hello from tests!",
            "title": "My Title",
        },
        blocking=True,
    )

    mock_send_message.assert_called_once_with(
        MOCK_RECIPIENT_ID, "*My Title*\nHello from tests!"
    )


async def test_send_message_e2e(
    hass: HomeAssistant,
    mock_config_entry_with_keys: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sending a message via notify entity (E2E mode)."""
    mock_config_entry_with_keys.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_keys.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry_with_keys.entry_id
    )
    notify_entities = [e for e in entities if e.domain == NOTIFY_DOMAIN]
    assert len(notify_entities) == 1

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "send_message",
        {"entity_id": notify_entities[0].entity_id, "message": "Hello E2E!"},
        blocking=True,
    )

    mock_send_message.assert_called_once_with(MOCK_RECIPIENT_ID, "Hello E2E!")


@pytest.mark.parametrize(
    "side_effect",
    [
        ThreemaSendError("Send failed"),
        ThreemaConnectionError("Connection error"),
    ],
    ids=["send_error", "connection_error"],
)
async def test_send_message_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
    entity_registry: er.EntityRegistry,
    side_effect: Exception,
) -> None:
    """Test notify entity raises HomeAssistantError on send/connection errors."""
    mock_send_message.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
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


async def test_send_message_auth_error_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test ThreemaAuthError during send raises error and starts reauth flow."""
    mock_send_message.side_effect = ThreemaAuthError("Token expired")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
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

    flows = hass.config_entries.flow.async_progress()
    assert any(
        f["context"]["source"] == config_entries.SOURCE_REAUTH
        and f["context"]["entry_id"] == mock_config_entry.entry_id
        for f in flows
    )
