"""Dataclass storing integration data in hass.data[DOMAIN]."""

from dataclasses import dataclass, field

from .coordinator import NASwebCoordinator, NotificationCoordinator


@dataclass
class NASwebData:
    """Class storing integration data."""

    notify_coordinator: NotificationCoordinator = field(
        default_factory=NotificationCoordinator
    )
    webhook_id = ""
    entries_coordinators: dict[str, NASwebCoordinator] = field(default_factory=dict)

    def is_initialized(self) -> bool:
        """Return True if instance was initialized and is ready for use."""
        return len(self.webhook_id) > 0
