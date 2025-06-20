"""Droplet Discovery API."""

import json
import logging


class DropletDiscovery:
    """Store Droplet discovery information."""

    def __init__(self, topic: str, payload: dict) -> None:
        """Initialize Droplet discovery."""
        self.device_id = payload.get("id")
        self.name = f"Droplet-{self.device_id}"
        self.data_topic = f"droplet-{self.device_id}/state"
        self.health_topic = f"droplet-{self.device_id}/health"

    def is_valid_discovery(self) -> bool:
        """Check if discovery packet contained all required data."""
        return self.device_id is not None


class Droplet:
    """Droplet device."""

    def __init__(self) -> None:
        """Initialize Droplet object."""
        self.logger = logging.getLogger(__name__)
        self.flow_rate = 0

    def parse_message(self, topic, payload, qos, retain) -> bool:
        """Parse Droplet MQTT message."""

        try:
            self.flow_rate = json.loads(payload)["flow_rate"]
        except (json.JSONDecodeError, KeyError):
            self.logger.warning("Failed to decode JSON")
            return False
        return True

    def get_flow_rate(self) -> float:
        """Retrieve Droplet's last flow rate."""
        return self.flow_rate
