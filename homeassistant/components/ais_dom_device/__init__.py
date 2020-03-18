"""
Support for interacting with Ais Dom devices.

For more details about this platform, please refer to the documentation at
https://www.ai-speaker.com
"""
import logging
import asyncio
import json

from homeassistant.core import callback
from .config_flow import configured_service
from .const import DOMAIN
from homeassistant.components.mqtt import discovery as mqtt_disco
from homeassistant.util.json import load_json, save_json

from . import sensor

_LOGGER = logging.getLogger(__name__)

PERSISTENCE_RF_ENTITIES = ".dom/.ais_rf_entities.json"
G_RF_CODES_DATA = None


@asyncio.coroutine
async def async_setup(hass, config):
    """Set up the Ais Dom devices platform."""
    global G_RF_CODES_DATA

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
    async def async_remove_ais_dom_device(call):
        if "device_id" not in call.data:
            return
        await _async_remove_ais_dom_device(hass, call.data["device_id"])

    @asyncio.coroutine
    async def async_start_rf_sniffing(call):
        await _async_start_rf_sniffing(hass)

    @asyncio.coroutine
    async def async_stop_rf_sniffing(call):
        clear = True
        if "clear" in call.data:
            clear = call.data["clear"]
        await _async_stop_rf_sniffing(hass, clear)

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
    hass.services.async_register(
        DOMAIN, "remove_ais_dom_device", async_remove_ais_dom_device
    )
    hass.services.async_register(DOMAIN, "start_rf_sniffing", async_start_rf_sniffing)
    hass.services.async_register(DOMAIN, "stop_rf_sniffing", async_stop_rf_sniffing)
    hass.services.async_register(DOMAIN, "send_rf_code", async_send_rf_code)

    G_RF_CODES_DATA = RFCodesData(hass)
    await G_RF_CODES_DATA.async_load()

    # discover the buttons
    for d in G_RF_CODES_DATA.rf_codes:
        topic = d["disco_topic"]
        payload = json.dumps(d["payload"])
        await hass.services.async_call(
            "mqtt", "publish", {"topic": topic, "payload": payload}
        )

    return True


async def _async_start_rf_sniffing(hass):
    # beep (00C0 is the length of the sound)
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": "AAC000C055"}
    )
    # set Portisch firmware support and messages
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": 1}
    )
    # start Bucket sniffing
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": 177}
    )
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": "AAB155"}
    )
    await asyncio.sleep(2)
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": 177}
    )
    # say info
    await hass.services.async_call(
        "ais_ai_service", "say_it", {"text": "Bramka RF w trybie nasłuchiwania"}
    )
    hass.states.async_set("sensor.ais_dom_mqtt_rf_sensor", "", {"codes": []})
    sensor.G_RF_CODES = []


async def _async_stop_rf_sniffing(hass, clear):
    # beep (00C0 is the length of the sound)
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": "AAC000C055"}
    )
    # set Portisch firmware support and messages
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": 1}
    )
    #  bucket Transmitting using command 0xB0
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": 176}
    )
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": "AAB055"}
    )
    await asyncio.sleep(2)
    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": 176}
    )
    # say info
    await hass.services.async_call(
        "ais_ai_service", "say_it", {"text": "Bramka RF w trybie transmisji"}
    )
    if clear:
        hass.states.async_set("sensor.ais_dom_mqtt_rf_sensor", "", {"codes": []})
        sensor.G_RF_CODES = []


async def _async_send_rf_code(hass, long_topic, b0_code):
    # get the first part of topic
    topic = long_topic.split("/")[0]
    # the command is like
    # cmnd/sonoffRFBridge/Backlog RfRaw AAB0210314016703F9241110011001010110011010110010101100255; RfRaw 0; RfRaw 1
    await hass.services.async_call(
        "mqtt",
        "publish",
        {
            "topic": topic + "/cmnd/Backlog",
            "payload": "RfRaw " + b0_code + "; RfRaw 0; RfRaw 1",
        },
    )


async def _async_remove_ais_dom_entity(hass, entity_id):
    ent_registry = await hass.helpers.entity_registry.async_get_registry()
    if ent_registry.async_is_registered(entity_id):
        entity_entry = ent_registry.async_get(entity_id)
        unique_id = entity_entry.unique_id
        domain = entity_entry.domain
        platform = entity_entry.platform
        ent_registry.async_remove(entity_id)
    # remove from already discovered
    if platform == "mqtt":
        discovery_hash = (domain, unique_id)
        if discovery_hash in hass.data[mqtt_disco.ALREADY_DISCOVERED]:
            mqtt_disco.clear_discovery_hash(hass, discovery_hash)
        # remove this code and his name from json
        G_RF_CODES_DATA.async_remove_code(unique_id)
    elif platform == "ais_drives_service":
        # remove drive, unmount and remove symlincs
        await hass.services.async_call(
            "ais_drives_service", "rclone_remove_drive", {"name": unique_id}
        )

    hass.states.async_remove(entity_id)


async def _async_remove_ais_dom_device(hass, device_id):
    dev_registry = await hass.helpers.device_registry.async_get_registry()
    device = dev_registry.async_get(device_id)

    # prepare list of entities to remove
    entities_to_remove = []
    ent_registry = await hass.helpers.entity_registry.async_get_registry()
    for e in ent_registry.entities:
        entity_entry = ent_registry.async_get(e)
        if entity_entry.device_id == device_id:
            entities_to_remove.append(entity_entry.entity_id)

    # remove ais dom entity
    for r in entities_to_remove:
        await _async_remove_ais_dom_entity(hass, r)

    if device is not None:
        dev_registry.async_remove_device(device_id)


async def _async_add_ais_dom_entity(hass, device_id, name, b0_code, topic, entity_type):
    # 0. get the device from registry
    registry = await hass.helpers.device_registry.async_get_registry()
    device = registry.async_get(device_id)

    # 1. get topic from payload
    unique_topic = topic.split("/")[0]

    # 2. execute the discovery for each code from json
    l_identifiers = list(device.identifiers)
    identifier = str(l_identifiers[0][-1])
    uniq_id = identifier + "_" + str(G_RF_CODES_DATA.get_len())

    if entity_type == "switch":
        uniq_id = "RL_" + uniq_id
        disco_topic = "homeassistant/switch/" + uniq_id + "/config"
        payload = {
            "name": name,
            "command_topic": unique_topic + "/cmnd/Backlog",
            "uniq_id": uniq_id,
            "payload_on": "RfRaw " + b0_code + "; RfRaw 0; RfRaw 1",
            "payload_off": "RfRaw " + b0_code + "; RfRaw 0; RfRaw 1",
            "device": {"identifiers": [identifier]},
        }
    else:
        uniq_id = "SNC_" + uniq_id
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

    # save this code and his name in json
    G_RF_CODES_DATA.async_add_or_update(name, disco_topic, payload, uniq_id)


class RFCodesData:
    """Class to hold RF codes list data."""

    def __init__(self, hass):
        """Initialize the bookmarks list."""
        self.hass = hass
        self.rf_codes = []

    def get_len(self):
        return len(self.rf_codes)

    @callback
    def async_add_or_update(self, name, disco_topic, payload, unique_id):
        """Update a rf_code list item."""
        item = next((itm for itm in self.rf_codes if itm["name"] == unique_id), None)

        if item is None:
            item = {
                "unique_id": unique_id,
                "name": name,
                "disco_topic": disco_topic,
                "payload": payload,
            }
            self.rf_codes.append(item)
        else:
            item.update(item)
        self.hass.async_add_job(self.save)
        return item

    @callback
    def async_remove_code(self, unique_id):
        """Reemove code """
        self.rf_codes = [
            itm for itm in self.rf_codes if not itm["unique_id"] == unique_id
        ]
        self.hass.async_add_job(self.save)

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
        """Save the rf_codes."""
        save_json(self.hass.config.path(PERSISTENCE_RF_ENTITIES), self.rf_codes)
