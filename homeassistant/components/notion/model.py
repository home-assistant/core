"""Define Notion model mixins."""

from dataclasses import dataclass

from aionotion.listener.models import ListenerKind


@dataclass(frozen=True, kw_only=True)
class NotionEntityDescription:
    """Define an description for Notion entities."""

    listener_kind: ListenerKind
