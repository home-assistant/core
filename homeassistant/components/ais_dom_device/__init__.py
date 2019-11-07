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
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.components.mqtt import discovery as mqtt_disco

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Ais Dom devices platform."""
    _LOGGER.info("async_setup Ais Dom devices platform.")

    # register services
    def convert_rf_code_b1_to_b0(call):
        if "code" not in call.data:
            _LOGGER.error("No code to convert")
            return
        _convert_rf_code_b1_to_b0(call.data["code"])

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
    hass.services.async_register(
        DOMAIN, "add_new_rf433_switch", async_add_new_rf433_switch
    )
    hass.services.async_register(
        DOMAIN, "remove_ais_dom_device", async_remove_ais_dom_device
    )

    return True


def _convert_rf_code_b1_to_b0(code):
    _LOGGER.info("TODO 123" + str(code))


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
