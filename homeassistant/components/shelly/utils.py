"""Shelly helpers functions."""
import logging
from typing import Optional

import aioshelly

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers import entity_registry

from . import ShellyDeviceWrapper

_LOGGER = logging.getLogger(__name__)


async def async_remove_entity_by_domain(hass, domain, unique_id, config_entry_id):
    """Remove entity by domain."""

    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    for entry in entity_registry.async_entries_for_config_entry(
        entity_reg, config_entry_id
    ):
        if entry.domain == domain and entry.unique_id == unique_id:
            entity_reg.async_remove(entry.entity_id)
            _LOGGER.debug("Removed %s domain for %s", domain, entry.original_name)
            break


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
            entity_name = wrapper.device.settings[mode][int(block.channel)].get("name")

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
