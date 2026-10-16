"""LoRaWAN device state."""

from dataclasses import dataclass, field

from lorawan_connection import (
    DeviceDescriptor,
    DeviceEvent,
    EventType,
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
    """Track connection metadata and backend observations."""

    configuration_url: str | None
    devices: dict[str, DeviceState] = field(default_factory=dict)

    def handle_device_event(self, event: DeviceEvent) -> bool:
        """Process a device event and return whether it was handled."""
        if event.type in (EventType.ADDED, EventType.UPDATED):
            if (state := self.devices.get(event.dev_eui)) is not None:
                state.descriptor = event.descriptor
            else:
                self.devices[event.dev_eui] = DeviceState(event.descriptor)
        elif event.type == EventType.REMOVED:
            self.devices.pop(event.dev_eui, None)
        else:
            state = self.devices.get(event.dev_eui)
            return state is not None and state.receive(event)
        return True
