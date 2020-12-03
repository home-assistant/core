"""Shelly helpers functions."""

from datetime import timedelta
import logging
from typing import Optional

import aioshelly

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.util.dt import parse_datetime, utcnow

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


def get_device_name(device: aioshelly.Device) -> str:
    """Naming for device."""
    return device.settings["name"] or device.settings["device"]["hostname"]


def get_entity_name(
    device: aioshelly.Device,
    block: aioshelly.Block,
    description: Optional[str] = None,
) -> str:
    """Naming for switch and sensors."""
    entity_name = get_device_name(device)

    if block:
        channels = None
        if block.type == "input":
            # Shelly Dimmer/1L has two input channels and missing "num_inputs"
            if device.settings["device"]["type"] in ["SHDM-1", "SHDM-2", "SHSW-L"]:
                channels = 2
            else:
                channels = device.shelly.get("num_inputs")
        elif block.type == "emeter":
            channels = device.shelly.get("num_emeters")
        elif block.type in ["relay", "light"]:
            channels = device.shelly.get("num_outputs")
        elif block.type in ["roller", "device"]:
            channels = 1

        channels = channels or 1

        if channels > 1 and block.type != "device":
            entity_name = None
            mode = block.type + "s"
            if mode in device.settings:
                entity_name = device.settings[mode][int(block.channel)].get("name")

            if not entity_name:
                if device.settings["device"]["type"] == "SHEM-3":
                    base = ord("A")
                else:
                    base = ord("1")
                entity_name = (
                    f"{get_device_name(device)} channel {chr(int(block.channel)+base)}"
                )

    if description:
        entity_name = f"{entity_name} {description}"

    return entity_name


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


def get_device_uptime(status: dict, last_uptime: str) -> str:
    """Return device uptime string, tolerate up to 5 seconds deviation."""
    uptime = utcnow() - timedelta(seconds=status["uptime"])

    if not last_uptime:
        return uptime.replace(microsecond=0).isoformat()

    if abs((uptime - parse_datetime(last_uptime)).total_seconds()) > 5:
        return uptime.replace(microsecond=0).isoformat()

    return last_uptime
