"""
Support for interacting with Ais Dom devices.

For more details about this platform, please refer to the documentation at
https://sviete.github.io/AIS-docs
"""
import logging
import asyncio
import json
from .config_flow import configured_service
from .const import DOMAIN
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry
from homeassistant.components.mqtt import discovery as mqtt_disco
from homeassistant.components.mqtt import subscription
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)
G_SUB_STATE = None


@asyncio.coroutine
async def async_setup(hass, config):
    """Set up the Ais Dom devices platform."""
    _LOGGER.info("async_setup Ais Dom devices platform.")

    # register services
    @asyncio.coroutine
    async def convert_rf_code_b1_to_b0(call):
        await _convert_rf_code_b1_to_b0(hass)

    @asyncio.coroutine
    async def send_b0_back_to_app(call):
        await _send_b0_back_to_app(hass)

    @asyncio.coroutine
    async def async_add_new_rf433_switch(call):
        if "name" not in call.data:
            return
        if "codes" not in call.data:
            return
        if "deviceId" not in call.data:
            return
        await _async_add_new_rf433_switch(
            hass, call.data["deviceId"], call.data["name"], call.data["codes"]
        )

    @asyncio.coroutine
    async def async_remove_ais_dom_device(call):
        if "entity_id" not in call.data:
            return
        await _async_remove_ais_dom_device(hass, call.data["entity_id"])

    """Set up the remove handler."""
    # hass.bus.async_listen(EVENT_ENTITY_REGISTRY_UPDATED, _handle_entry_remove)

    hass.services.async_register(
        DOMAIN, "convert_rf_code_b1_to_b0", convert_rf_code_b1_to_b0
    )
    hass.services.async_register(DOMAIN, "send_b0_back_to_app", send_b0_back_to_app)
    hass.services.async_register(
        DOMAIN, "add_new_rf433_switch", async_add_new_rf433_switch
    )
    hass.services.async_register(
        DOMAIN, "remove_ais_dom_device", async_remove_ais_dom_device
    )

    return True


@asyncio.coroutine
async def _send_b0_back_to_app(hass, call):
    _LOGGER.log("OK")
    # hass.add_job(
    #     hass.services.call("mqtt", "publish", {"topic": "aisdomrf", "payload": payload})
    # )


async def _convert_rf_code_b1_to_b0(hass):
    _LOGGER.info("TODO 123")

    await hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/RfRaw", "payload": "AAB155"}
    )
    _LOGGER.info("Call done")

    @callback
    def decode_rf(msg):
        """Record calls."""
        _LOGGER.info("xxx")
        _LOGGER.info("message: " + str(msg.payload))
        try:
            payload = json.loads(msg.payload)
            if "RfRaw" in payload:
                code = payload.get("RfRaw")["Data"]
                # TODO decode
                _LOGGER.info(code)

                # TODO get device topic from message
                topic = msg.topic
                _LOGGER.info(topic)
                device_topic = "sonoffRFBridge"

                payload = {
                    "code": "xxx" + code,
                    "command_topic": "cmnd/" + device_topic + "/Backlog",
                }
                # TODO return without blocking...
                # hass.services.call("ais_dom_device", "send_b0_back_to_app", payload)
                # return asyncio.run_coroutine_threadsafe(
                #     _send_b0_back_to_app(hass, json.dumps(payload)), hass.loop
                # ).result()

        except Exception as e:
            _LOGGER.info("Error: " + str(e))

    sub_state = None
    sub_state = await subscription.async_subscribe_topics(
        hass,
        sub_state,
        {"state_topic": {"topic": "+/tele/RESULT", "msg_callback": decode_rf}},
    )


async def _async_remove_ais_dom_device(hass, entity_id):
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


async def _async_add_new_rf433_switch(hass, device_id, name, codes):
    # 0. get the device from registry
    registry = await dr.async_get_registry(hass)
    device = registry.async_get(device_id)

    # 1. get topic from payload
    device_topic = "sonoffRFBridge"

    # 2. select the best code and convert it to B0

    # 3. save this code and his mane in json

    # 4. execute the discovery for each code from json
    l_identifiers = list(device.identifiers)
    identifier = str(l_identifiers[0][-1])
    disco_topic = "homeassistant/switch/" + identifier + "_RL_123/config"
    uniq_id = identifier + "_RL_123"
    payload = {
        "name": name,
        "command_topic": "cmnd/" + device_topic + "/Backlog",
        "uniq_id": uniq_id,
        "payload_on": "RfRaw AAB0210314016703F92418010101100110011001010110011001100101; RfRaw 0",
        "payload_off": "RfRaw AAB0210314016703F92418010101100110011001010110011001100101; RfRaw 0",
        "device": {"identifiers": [identifier]},
    }
    await hass.services.async_call(
        "mqtt", "publish", {"topic": disco_topic, "payload": json.dumps(payload)}
    )
