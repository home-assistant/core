"""Define Notion model mixins."""
from dataclasses import dataclass

from aionotion.sensor.models import ListenerKind


@dataclass(frozen=True)
class NotionEntityDescriptionMixin:
    """Define an description mixin Notion entities."""

    listener_kind: ListenerKind
