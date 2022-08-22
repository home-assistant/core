"""Define a gateway class for managing MQTT connections within the gateway"""

import asyncio
import json
import logging

from homeassistant.components.mqtt import MQTT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import MQTT_CLIENT_INSTANCE, CONF_LIGHT_DEVICE_TYPE, EVENT_ENTITY_REGISTER, MQTT_TOPIC_PREFIX

_LOGGER = logging.getLogger(__name__)


class Gateway:
    """Class for gateway and managing MQTT connections within the gateway"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Init dummy hub."""
        self._hass = hass
        self._entry = entry
        self._id = entry.data[CONF_NAME]

        self.light_group_map = {}
        self.room_map = {}

        """Lighting Control Type"""
        self.light_device_type = entry.data[CONF_LIGHT_DEVICE_TYPE]

    async def connect(self):
        """Connect to gateway internal MQTT"""

        self._hass.data[MQTT_CLIENT_INSTANCE] = MQTT(
            self._hass,
            self._entry,
            self._entry.data,
        )

        await self._hass.data[MQTT_CLIENT_INSTANCE].async_connect()

        async def async_stop_mqtt(_event: Event):
            """Stop MQTT component."""
            await self.disconnect()

        self._hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_mqtt)

    async def disconnect(self):
        """Disconnect gateway MQTT connection"""

        mqtt_client: MQTT = self._hass.data[MQTT_CLIENT_INSTANCE]

        await mqtt_client.async_disconnect()

    async def _async_mqtt_subscribe(self, msg):
        """Process received MQTT messages"""

        payload = msg.payload
        topic = msg.topic

        if payload:
            try:
                payload = json.loads(payload)
            except ValueError:
                _LOGGER.warning("Unable to parse JSON: '%s'", payload)
                return
        else:
            _LOGGER.warning("JSON None")
            return

        if topic.endswith("p5"):
            """Device List data"""
            device_list = payload["data"]["list"]
            for device in device_list:
                device_type = device["devType"]
                device["unique_id"] = f"{device['sn']}"
                if device_type == 3:
                    """Curtain"""
                    await self._add_entity("cover", device)
                elif device_type == 1 and self.light_device_type == "single":
                    """Light"""
                    device["is_group"] = False
                    await self._add_entity("light", device)
        elif topic.endswith("p28"):
            """Scene List data"""
            scene_list = payload["data"]
            for scene in scene_list:
                scene["unique_id"] = f"{scene['id']}"
                await self._add_entity("scene", scene)
        elif topic.endswith("event/3"):
            """Device state data"""
            stats_list = payload["data"]
            for state in stats_list:
                async_dispatcher_send(
                    self._hass, "mhtzn_device_state_{}".format(state["sn"]), state
                )
        elif topic.endswith("p33"):
            """Basic data, including room information, light group information, curtain group information"""
            for room in payload["data"]["rooms"]:
                self.room_map[room["id"]] = room
            for lightGroup in payload["data"]["lightsSubgroups"]:
                self.light_group_map[lightGroup["id"]] = lightGroup
        elif topic.endswith("p31"):
            """Relationship data for rooms and groups"""
            for room in payload["data"]:
                room_id = room["room"]
                room_name = "默认房间"
                if room_id == 0:
                    room_name = "全屋"
                elif room_id in self.room_map:
                    room_instance = self.room_map[room_id]
                    room_name = room_instance["name"]

                for light_group_id in room["lights"]:
                    device_name = "默认灯组"
                    if light_group_id == 0:
                        device_name = "所有灯"
                    elif light_group_id in self.light_group_map:
                        light_group = self.light_group_map[light_group_id]
                        device_name = light_group["name"]

                    group = {
                        "unique_id": f"{room_id}-{light_group_id}",
                        "room": room_id,
                        "subgroup": light_group_id,
                        "is_group": True,
                        "name": f"{room_name}-{device_name}",
                    }
                    await self._add_entity("light", group)

    async def _add_entity(self, component: str, device: dict):
        """Add child device information"""
        async_dispatcher_send(
            self._hass, EVENT_ENTITY_REGISTER.format(component), device
        )

    async def reconnect(self, entry: ConfigEntry):
        """Reconnect gateway MQTT"""
        mqtt_client: MQTT = self._hass.data[MQTT_CLIENT_INSTANCE]
        mqtt_client.conf = entry.data
        await mqtt_client.async_disconnect()
        mqtt_client.init_client()
        await mqtt_client.async_connect()

    async def init(self):
        """Initialize the gateway business logic, including subscribing to device data, scene data, and basic data,
        and sending data reporting instructions to the gateway"""
        discovery_topics = [
            # Subscribe to device list
            f"{MQTT_TOPIC_PREFIX}/center/p5",
            # Subscribe to scene list
            f"{MQTT_TOPIC_PREFIX}/center/p28",
            # Subscribe to all basic data Room list, light group list, curtain group list
            f"{MQTT_TOPIC_PREFIX}/center/p33",
            # Subscribe to room and light group relationship
            f"{MQTT_TOPIC_PREFIX}/center/p31",
            # Subscribe to device property change events
            "p/+/event/3",
        ]
        await asyncio.gather(
            *(
                self._hass.data[MQTT_CLIENT_INSTANCE].async_subscribe(
                    topic,
                    self._async_mqtt_subscribe,
                    0,
                    "utf-8"
                )
                for topic in discovery_topics
            )
        )
        await asyncio.sleep(5)
        mqtt_connected = self._hass.data[MQTT_CLIENT_INSTANCE].connected

        _LOGGER.warning(mqtt_connected)

        if mqtt_connected:
            # publish payload to get device list
            await self._async_mqtt_publish("P/0/center/q5")
            # publish payload to get scene list
            await self._async_mqtt_publish("P/0/center/q28")
            if self.light_device_type == "group":
                # publish payload to get all basic data Room list, light group list, curtain group list
                await self._async_mqtt_publish("P/0/center/q33")
                # publish payload to get room and light group relationship
                await asyncio.sleep(5)
                await self._async_mqtt_publish("P/0/center/q31")

    async def _async_mqtt_publish(self, topic: str):
        query_device_payload = {
            "seq": 1,
            "rspTo": MQTT_TOPIC_PREFIX,
            "data": {}
        }
        await self._hass.data[MQTT_CLIENT_INSTANCE].async_publish(
            topic,
            json.dumps(query_device_payload),
            0,
            False
        )
