"""OpenTherm Controller."""
from typing import Any

from requests import Response


class OpenThermController:
    """Class that represents the data object that holds the data."""

    def __init__(self, response: Response) -> None:
        """Initiatlize."""
        json = response.json()
        self.device_id = json.get("deviceId")
        self.dhw_setpoint = json.get("dhwSetpoint")
        self.chw_setpoint = json.get("chwSetpoint")
        self.room_setpoint = json.get("roomSetpoint")
        self.away = json.get("away")
        self.enabled = json.get("enabled")
        self.chw_temperature = json.get("chwTemperature")
        self.dhw_temperature = json.get("dhwTemperature")
        self.room_temperature = json.get("roomTemperature")
        self.outside_temperature = json.get("outsideTemperature")
        self.chw_active = json.get("chwActive")
        self.dhw_active = json.get("dhwActive")

    def get_json(self) -> dict[str, Any]:
        """Get json."""
        data = {
            "deviceId": self.device_id,
            "enabled": self.enabled,
            "roomSetpoint": self.room_setpoint,
            "dhwSetpoint": self.dhw_setpoint,
            "away": self.away,
        }

        return data
