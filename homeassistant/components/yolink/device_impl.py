"""YoLink Special Device Implement."""

from homeassistant.components.yolink.device import YoLinkDevice
from homeassistant.components.yolink.entities import (
    YoLinkBatteryEntity,
    YoLinkDoorEntity,
)


class YoLinkDoorSensor(YoLinkDevice):
    """YoLink DoorSensor Implement."""

    def __init__(self, device: dict, hass, config_entry):
        """Initialize the YoLink Door Sensor."""
        YoLinkDevice.__init__(self, device, hass, config_entry)
        self.door_entity = YoLinkDoorEntity(self, config_entry)
        self.battery_entity = YoLinkBatteryEntity(self, config_entry)
        self.entities.append(self.door_entity)
        self.entities.append(self.battery_entity)

    async def parse_state(self, state):
        """Parse Door Sensor state from data."""
        await self.door_entity.udpate_entity_state(state["state"] == "open")
        await self.battery_entity.udpate_entity_state(state["battery"])
