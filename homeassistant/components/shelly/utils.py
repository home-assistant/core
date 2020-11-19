"""Shelly helpers functions."""

from datetime import datetime, timedelta
import logging
from typing import Optional

import aioshelly

from homeassistant.components.sensor import DEVICE_CLASS_TIMESTAMP
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT

from . import ShellyDeviceWrapper
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_remove_shelly_entity(hass, domain, unique_id):
    """Remove a Shelly entity."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    entity_id = entity_reg.async_get_entity_id(domain, DOMAIN, unique_id)
    if entity_id:
        _LOGGER.debug("Removing entity: %s", entity_id)
        entity_reg.async_remove(entity_id)


def temperature_unit(block_info: dict) -> str:
    """Detect temperature unit."""
    if block_info[aioshelly.BLOCK_VALUE_UNIT] == "F":
        return TEMP_FAHRENHEIT
    return TEMP_CELSIUS


def get_entity_name(
    wrapper: ShellyDeviceWrapper,
    block: aioshelly.Block,
    description: Optional[str] = None,
):
    """Naming for switch and sensors."""
    entity_name = wrapper.name

    if block:
        channels = None
        if block.type == "input":
            channels = wrapper.device.shelly.get("num_inputs")
        elif block.type == "emeter":
            channels = wrapper.device.shelly.get("num_emeters")
        elif block.type in ["relay", "light"]:
            channels = wrapper.device.shelly.get("num_outputs")
        elif block.type in ["roller", "device"]:
            channels = 1

        channels = channels or 1

        if channels > 1 and block.type != "device":
            entity_name = None
            mode = block.type + "s"
            if mode in wrapper.device.settings:
                entity_name = wrapper.device.settings[mode][int(block.channel)].get(
                    "name"
                )

            if not entity_name:
                if wrapper.model == "SHEM-3":
                    base = ord("A")
                else:
                    base = ord("1")
                entity_name = f"{wrapper.name} channel {chr(int(block.channel)+base)}"

        # Shelly Dimmer has two input channels and missing "num_inputs"
        if wrapper.model in ["SHDM-1", "SHDM-2"] and block.type == "input":
            entity_name = f"{entity_name} channel {int(block.channel)+1}"

    if description:
        entity_name = f"{entity_name} {description}"

    return entity_name


def get_rest_value_from_path(status, device_class, path: str):
    """Parser for REST path from device status."""

    if "/" not in path:
        attribute_value = status[path]
    else:
        attribute_value = status[path.split("/")[0]][path.split("/")[1]]
    if device_class == DEVICE_CLASS_TIMESTAMP:
        last_boot = datetime.utcnow() - timedelta(seconds=attribute_value)
        attribute_value = last_boot.replace(microsecond=0).isoformat()

    if "new_version" in path:
        attribute_value = attribute_value.split("/")[1].split("@")[0]

    return attribute_value


def is_momentary_input(settings: dict, block: aioshelly.Block) -> bool:
    """Return true if input button settings is set to a momentary type."""
    button = settings.get("relays") or settings.get("lights") or settings.get("inputs")

    # Shelly 1L has two button settings in the first channel
    if settings["device"]["type"] == "SHSW-L":
        channel = int(block.channel or 0) + 1
        button_type = button[0].get("btn" + str(channel) + "_type")
    else:
        # Some devices has only one channel in settings
        channel = min(int(block.channel or 0), len(button) - 1)
        button_type = button[channel].get("btn_type")

    return button_type in ["momentary", "momentary_on_release"]
