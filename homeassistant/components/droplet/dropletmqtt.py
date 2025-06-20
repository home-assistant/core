"""Droplet API."""

import json


class DropletDiscovery:
    """Store Droplet discovery information."""

    device_id: str | None
    name: str
    data_topic: str | None
    health_topic: str | None

    fw_version: str | None
    manufacturer: str | None
    serial_number: str | None
    model: str | None

    def __init__(self, topic: str, payload: dict) -> None:
        """Initialize Droplet discovery."""
        self.data_topic = payload.get("state_topic")
        self.health_topic = payload.get("availability_topic")

        # Device metadata
        dev_info: dict | None
        if dev_info := payload.get("dev"):
            self.device_id = dev_info.get("ids")
            self.name = f"Droplet-{self.device_id}"
            self.fw_version = dev_info.get("fw")
            self.manufacturer = dev_info.get("mf")
            self.serial_number = dev_info.get("sn")
            self.model = dev_info.get("mdl")

    def is_valid(self) -> bool:
        """Check if discovery packet contained all required data."""
        if (
            not self.device_id
            or not self.data_topic
            or not self.health_topic
            or self.device_id not in self.data_topic
            or self.device_id not in self.health_topic
        ):
            return False
        return True


class Droplet:
    """Droplet device."""

    def __init__(self) -> None:
        """Initialize Droplet object."""
        self.flow_rate = 0
        self.available = True

    def parse_message(
        self, topic: str, payload: str | bytes | bytearray, qos: int, retain: bool
    ) -> bool:
        """Parse Droplet MQTT message."""
        try:
            msg_type = topic.split("/")[1]
        except IndexError:
            return False

        match msg_type:
            case "state":
                try:
                    msg = json.loads(payload)
                except json.JSONDecodeError:
                    return False
                return self._parse_state_message(msg)
            case "health":
                self.available = str(payload) == "online"

        return True

    def _parse_state_message(self, msg: dict) -> bool:
        """Parse state message and return true if anything changed."""
        changed = False
        if flow_rate := msg.get("flow_rate"):
            self.flow_rate = flow_rate
            changed = True
        return changed

    def get_flow_rate(self) -> float:
        """Retrieve Droplet's last flow rate."""
        return self.flow_rate

    def get_availability(self) -> bool:
        """Return true if device is available, false otherwise."""
        return self.available
