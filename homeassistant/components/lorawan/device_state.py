"""LoRaWAN device state."""

from dataclasses import dataclass, replace

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


class ObservedConnection:
    """Keep connection metadata and observations through transport outages."""

    def __init__(
        self,
        configuration_url: str | None,
        previous: ObservedConnection | None = None,
    ) -> None:
        """Initialize connection observations."""
        self.configuration_url = configuration_url
        self.devices: dict[str, DeviceState] = {}
        self._previous_devices = previous.devices if previous else {}

    def handle_device_event(self, event: DeviceEvent) -> bool:
        """Process a device event and return whether it was handled."""
        if event.type in (EventType.ADDED, EventType.UPDATED):
            if (state := self.devices.get(event.dev_eui)) is not None:
                state.descriptor = event.descriptor
            elif (previous := self._previous_devices.get(event.dev_eui)) is not None:
                self.devices[event.dev_eui] = replace(
                    previous, descriptor=event.descriptor
                )
            else:
                self.devices[event.dev_eui] = DeviceState(event.descriptor)
        elif event.type == EventType.REMOVED:
            self.devices.pop(event.dev_eui, None)
        else:
            state = self.devices.get(event.dev_eui)
            return state is not None and state.receive(event)
        return True

    def finish_replay(self) -> None:
        """Release observations from the previous connection."""
        self._previous_devices = {}
