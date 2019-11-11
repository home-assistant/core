"""
Support for interacting with Ais Dom devices.

For more details about this platform, please refer to the documentation at
https://sviete.github.io/AIS-docs
"""
import logging
import asyncio
import json

from homeassistant.core import callback
from .config_flow import configured_service
from .const import DOMAIN
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry
from homeassistant.components.mqtt import discovery as mqtt_disco
from homeassistant.util.json import load_json, save_json

from . import sensor

_LOGGER = logging.getLogger(__name__)

PERSISTENCE_RF_ENTITIES = ".dom/.ais_rf_entities.json"


@asyncio.coroutine
async def async_setup(hass, config):
    """Set up the Ais Dom devices platform."""
    _LOGGER.info("async_setup Ais Dom devices platform.")

    # register services
    @asyncio.coroutine
    async def add_ais_dom_entity(call):
        if "name" not in call.data:
            return
        if "code" not in call.data:
            return
        if "deviceId" not in call.data:
            return
        if "topic" not in call.data:
            return
        if "type" not in call.data:
            return
        await _async_add_ais_dom_entity(
            hass,
            call.data["deviceId"],
            call.data["name"],
            call.data["code"],
            call.data["topic"],
            call.data["type"],
        )

    @asyncio.coroutine
    async def async_remove_ais_dom_entity(call):
        if "entity_id" not in call.data:
            return
        await _async_remove_ais_dom_entity(hass, call.data["entity_id"])

    @asyncio.coroutine
    async def async_start_rf_sniffing(call):
        await _async_start_rf_sniffing(hass)

    @asyncio.coroutine
    async def async_stop_rf_sniffing(call):
        await _async_stop_rf_sniffing(hass)

    @asyncio.coroutine
    async def async_send_rf_code(call):
        if "code" not in call.data:
            return
        if "topic" not in call.data:
            return
        await _async_send_rf_code(hass, call.data["topic"], call.data["code"])

    hass.services.async_register(DOMAIN, "add_ais_dom_entity", add_ais_dom_entity)
    hass.services.async_register(
        DOMAIN, "remove_ais_dom_entity", async_remove_ais_dom_entity
    )
    hass.services.async_register(DOMAIN, "start_rf_sniffing", async_start_rf_sniffing)
    hass.services.async_register(DOMAIN, "stop_rf_sniffing", async_stop_rf_sniffing)
    hass.services.async_register(DOMAIN, "send_rf_code", async_send_rf_code)

    rf_codes_data = hass.data[DOMAIN] = RFCodesData(hass)
    await rf_codes_data.async_load()

    return True


async def _async_start_rf_sniffing(hass):
    # start Bucket sniffing using command 0xB1
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": 177}
    )
    # beep (00C0 is the length of the sound)
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": "AAC000C055"}
    )
    # say info
    await hass.services.async_call(
        "ais_ai_service", "say_it", {"text": "Bramka RF w trybie nasłuchiwania"}
    )
    hass.states.async_set("sensor.ais_dom_mqtt_rf_sensor", "", {"codes": []})
    sensor.G_RF_CODES = []


async def _async_stop_rf_sniffing(hass):
    #  bucket Transmitting using command 0xB0
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": 176}
    )
    # beep (00C0 is the length of the sound)
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": "AAC000C055"}
    )
    # say info
    await hass.services.async_call(
        "ais_ai_service", "say_it", {"text": "Bramka RF w trybie transmisji"}
    )
    hass.states.async_set("sensor.ais_dom_mqtt_rf_sensor", "", {"codes": []})
    sensor.G_RF_CODES = []


async def _async_send_rf_code(hass, long_topic, b0_code):
    # get the first part of topic
    topic = long_topic.split("/")[0]
    # the command is like
    # cmnd/sonoffRFBridge/Backlog RfRaw AAB0210314016703F92411100110010101100110011001010110010101100255; RfRaw 0
    await hass.services.async_call(
        "mqtt",
        "publish",
        {
            "topic": "cmnd/" + topic + "/Backlog",
            "payload": "RfRaw " + b0_code + "; RfRaw 0",
        },
    )


async def _async_remove_ais_dom_entity(hass, entity_id):
    registry = await entity_registry.async_get_registry(hass)
    if entity_id in registry.entities:
        entity_entry = registry.async_get(entity_id)
        unique_id = entity_entry.unique_id
        domain = entity_entry.domain
        platform = entity_entry.platform
        registry.async_remove(entity_id)
        # remove from already discovered
        if platform == "mqtt":
            discovery_hash = (domain, unique_id)
            mqtt_disco.clear_discovery_hash(hass, discovery_hash)

    hass.states.async_remove(entity_id)


async def _async_add_ais_dom_entity(hass, device_id, name, b0_code, topic, entity_type):
    # 0. get the device from registry
    registry = await dr.async_get_registry(hass)
    device = registry.async_get(device_id)

    # 1. get topic from payload
    unique_topic = topic.split("/")[0]

    # 2. save this code and his name in json

    # 3. execute the discovery for each code from json
    l_identifiers = list(device.identifiers)
    identifier = str(l_identifiers[0][-1])
    # TODO
    uniq_id = identifier + "123"

    if entity_type == "switch":
        uniq_id = "_RL_" + uniq_id
        disco_topic = "homeassistant/switch/" + uniq_id + "/config"
        payload = {
            "name": name,
            "command_topic": "cmnd/" + unique_topic + "/Backlog",
            "uniq_id": uniq_id,
            "payload_on": "RfRaw " + b0_code + "; RfRaw 0",
            "payload_off": "RfRaw " + b0_code + "; RfRaw 0",
            "device": {"identifiers": [identifier]},
        }
    else:
        uniq_id = "_SNC_" + uniq_id
        disco_topic = "homeassistant/sensor/" + uniq_id + "/config"
        payload = {
            "name": name,
            "uniq_id": uniq_id,
            "device": {"identifiers": [identifier]},
            "availability_topic": b0_code,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device_class": "timestamp",
        }

    await hass.services.async_call(
        "mqtt", "publish", {"topic": disco_topic, "payload": json.dumps(payload)}
    )


class RFCodesData:
    """Class to hold RF codes list data."""

    def __init__(self, hass):
        """Initialize the bookmarks list."""
        self.hass = hass
        self.rf_codes = []

    @callback
    def async_add(self, call, rf_code):
        """Add a item."""

        attributes = {}
        item = {"name": "full_name", "id": "uuid.uuid4().hex", "source": "audio_type"}
        self.rf_codes.append(item)
        self.hass.async_add_job(self.save, True)

        return item

    @callback
    def async_update(self, item_id, info):
        """Update a rf_code list item."""
        item = next((itm for itm in self.bookmarks if itm["id"] == item_id), None)

        if item is None:
            raise KeyError

        item.update(info)
        self.hass.async_add_job(self.save)
        return item

    @callback
    def async_remove_code(self, item_id):
        """Reemove bookmark """
        self.rf_codes = [itm for itm in self.bookmarks if not itm["id"] == item_id]
        self.hass.async_add_job(self.save, True)

    @asyncio.coroutine
    def async_load(self):
        """Load codes."""

        def load():
            """Load the codes synchronously."""
            try:
                self.rf_codes = load_json(
                    self.hass.config.path(PERSISTENCE_RF_ENTITIES), default=[]
                )
            except Exception as e:
                _LOGGER.error("Can't load rf_codes data: " + str(e))

        yield from self.hass.async_add_job(load)

    def save(self):
        """Save the bookmarks and favorites."""
        self.rf_codes = self.bookmarks[-50:]
        save_json(self.hass.config.path(PERSISTENCE_RF_ENTITIES), self.bookmarks)
        self.hass.async_add_job(
            self.hass.services.async_call(DOMAIN, PERSISTENCE_RF_ENTITIES)
        )
