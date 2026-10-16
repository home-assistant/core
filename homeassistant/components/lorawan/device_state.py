"""LoRaWAN device state."""

from dataclasses import dataclass, field

from lorawan_connection import (
    DeviceDescriptor,
    DeviceEvent,
    JoinEvent,
    StatusEvent,
    UplinkEvent,
)


@dataclass
class DeviceState:
    """Keep the latest observations independently of a device integration."""

    descriptor: DeviceDescriptor
    uplink: UplinkEvent | None = None
    join: JoinEvent | None = None
    status: StatusEvent | None = None

    def receive(self, event: DeviceEvent) -> bool:
        """Store observations without replacing newer data with a delayed event."""
        if isinstance(event, UplinkEvent):
            if self.uplink is not None and event.received_at < self.uplink.received_at:
                return False
            self.uplink = event
        elif isinstance(event, JoinEvent):
            if self.join is not None and event.received_at < self.join.received_at:
                return False
            self.join = event
        elif isinstance(event, StatusEvent):
            if self.status is not None and event.received_at < self.status.received_at:
                return False
            self.status = event
        else:
            return False
        return True


@dataclass
class ObservedConnection:
    """Keep connection metadata and observations through transport outages."""

    configuration_url: str | None
    devices: dict[str, DeviceState] = field(default_factory=dict)
