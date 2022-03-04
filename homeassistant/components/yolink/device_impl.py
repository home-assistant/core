"""YoLink Special Device Implement."""

from homeassistant.components.yolink.device import YoLinkDevice
from homeassistant.components.yolink.entities import (
    YoLinkBatteryEntity,
    YoLinkDoorEntity,
    YoLinkHumidityEntity,
    YoLinkLeakEntity,
    YoLinkLightEntity,
    YoLinkMotionEntity,
    YoLinkSirenEntity,
    YoLinkTemperatureEntity,
)
from homeassistant.components.yolink.model import BRDP


class YoLinkOutlet(YoLinkDevice):
    """Representation of a YoLink Outlet."""

    def __init__(self, device: dict, hass, config_entry):
        """Initialize the YoLink Sensor."""
        YoLinkDevice.__init__(self, device, hass, config_entry)
        self.light_entity = YoLinkLightEntity(self, "Outlet", config_entry)
        self.entities.append(self.light_entity)

    async def async_turn_on_off(self, state: bool):
        """Call *.getState with device to fetch realtime state data."""
        resp = await self.call_device_http_api(
            "setState", {"state": ("open" if state else "close")}
        )
        self.logger.info("call outlet state change api")
        await self.parse_state(resp.data)
        return resp

    def resolve_state_in_event(self, data: BRDP, event_type: str):
        """Get device state in BRDP."""
        if event_type == "setState":
            return data.data
        return super().resolve_state_in_event(data, event_type)

    async def parse_state(self, state):
        """Parse T&H Sensor state from data."""
        await self.light_entity.udpate_entity_state(state["state"] == "open")


class YoLinkSiren(YoLinkDevice):
    """Representation of a YoLink Siren."""

    def __init__(self, device: dict, hass, config_entry):
        """Initialize the YoLink Sensor."""
        YoLinkDevice.__init__(self, device, hass, config_entry)
        self.siren_entiry = YoLinkSirenEntity(self, "Siren", config_entry)
        self.entities.append(self.siren_entiry)

    async def async_turn_on_off(self, state: bool):
        """Call *.getState with device to fetch realtime state data."""
        resp = await self.call_device_http_api("setState", {"state": {"alarm": state}})
        await self.parse_state(resp.data)
        return resp

    async def parse_state(self, state):
        """Parse T&H Sensor state from data."""
        await self.siren_entiry.udpate_entity_state(state["state"] == "alert")


class YoLinkTempHumiditySensor(YoLinkDevice):
    """YoLink THSensor Implement."""

    def __init__(self, device: dict, hass, config_entry):
        """Initialize the YoLink THSensor."""
        YoLinkDevice.__init__(self, device, hass, config_entry)
        self.humidity_entity = YoLinkHumidityEntity(self, config_entry)
        self.temperature_entity = YoLinkTemperatureEntity(self, config_entry)
        self.battery_entity = YoLinkBatteryEntity(self, config_entry)
        self.entities.append(self.humidity_entity)
        self.entities.append(self.temperature_entity)
        self.entities.append(self.battery_entity)

    async def parse_state(self, state):
        """Parse T&H Sensor state from data."""
        await self.humidity_entity.udpate_entity_state(state["humidity"])
        await self.temperature_entity.udpate_entity_state(state["temperature"])
        await self.battery_entity.udpate_entity_state(state["battery"])


class YoLinkMotionSensor(YoLinkDevice):
    """YoLink MotionSensor Implement."""

    def __init__(self, device: dict, hass, config_entry):
        """Initialize the YoLink Motion Sensor."""
        YoLinkDevice.__init__(self, device, hass, config_entry)
        self.motion_entity = YoLinkMotionEntity(self, config_entry)
        self.battery_entity = YoLinkBatteryEntity(self, config_entry)
        self.entities.append(self.motion_entity)
        self.entities.append(self.battery_entity)

    async def parse_state(self, state):
        """Parse Motion Sensor state from data."""
        await self.motion_entity.udpate_entity_state(state["state"] == "alert")
        await self.battery_entity.udpate_entity_state(state["battery"])


class YoLinkLeakSensor(YoLinkDevice):
    """YoLink LeakSensor Implement."""

    def __init__(self, device: dict, hass, config_entry):
        """Initialize the YoLink Leak Sensor."""
        YoLinkDevice.__init__(self, device, hass, config_entry)
        self.leak_entity = YoLinkLeakEntity(self, config_entry)
        self.battery_entity = YoLinkBatteryEntity(self, config_entry)
        self.entities.append(self.leak_entity)
        self.entities.append(self.battery_entity)

    async def parse_state(self, state):
        """Parse Leak Sensor state from data."""
        await self.leak_entity.udpate_entity_state(
            state["state"] == "alert" or state["state"] == "full"
        )
        await self.battery_entity.udpate_entity_state(state["battery"])


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
