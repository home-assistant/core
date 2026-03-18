"""Typed websocket payload models."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class ContextPayload(TypedDict):
    """Serialized Home Assistant context."""

    id: str
    parent_id: str | None
    user_id: str | None


class CommandMessage(TypedDict):
    """Base outbound websocket command."""

    id: int
    type: str


class CommandResultMessage(TypedDict):
    """Inbound websocket command result."""

    id: int
    type: str
    success: bool
    result: Any
    error: NotRequired[dict[str, Any]]


class EventPayload(TypedDict):
    """Inbound websocket event wrapper."""

    event_type: str
    time_fired: str
    origin: str
    context: ContextPayload
    data: dict[str, Any]


class EventMessage(TypedDict):
    """Inbound websocket subscription event."""

    id: int
    type: str
    event: EventPayload


class StatePayload(TypedDict):
    """Serialized state from the websocket API."""

    entity_id: str
    state: str
    attributes: dict[str, Any]
    last_changed: str
    last_updated: str
    last_reported: NotRequired[str]
    context: ContextPayload


class EntityRegistryEntryPayload(TypedDict):
    """Serialized entity registry entry from config websocket commands."""

    entity_id: str
    id: str
    platform: str
    unique_id: str
    area_id: str | None
    categories: dict[str, str]
    config_entry_id: str | None
    config_subentry_id: str | None
    created_at: float | str
    device_id: str | None
    disabled_by: str | None
    entity_category: str | None
    has_entity_name: bool
    hidden_by: str | None
    icon: str | None
    labels: list[str]
    modified_at: float | str
    name: str | None
    options: dict[str, Any]
    original_name: str | None
    translation_key: str | None
    aliases: NotRequired[list[str]]
    capabilities: NotRequired[dict[str, Any] | None]
    device_class: NotRequired[str | None]
    original_device_class: NotRequired[str | None]
    original_icon: NotRequired[str | None]
