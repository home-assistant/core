"""Shelly helpers functions."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Final, cast

from aioshelly.block_device import BLOCK_VALUE_UNIT, COAP, Block, BlockDevice
from aioshelly.const import MODEL_NAMES
from aioshelly.rpc_device import RpcDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import singleton
from homeassistant.helpers.typing import EventType
from homeassistant.util.dt import utcnow

from .const import (
    BASIC_INPUTS_EVENTS_TYPES,
    CONF_COAP_PORT,
    DEFAULT_COAP_PORT,
    DOMAIN,
    MAX_RPC_KEY_INSTANCES,
    RPC_INPUTS_EVENTS_TYPES,
    SHBTN_INPUTS_EVENTS_TYPES,
    SHBTN_MODELS,
    SHIX3_1_INPUTS_EVENTS_TYPES,
    UPTIME_DEVIATION,
)

_LOGGER: Final = logging.getLogger(__name__)


async def async_remove_shelly_entity(
    hass: HomeAssistant, domain: str, unique_id: str
) -> None:
    """Remove a Shelly entity."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    entity_id = entity_reg.async_get_entity_id(domain, DOMAIN, unique_id)
    if entity_id:
        _LOGGER.debug("Removing entity: %s", entity_id)
        entity_reg.async_remove(entity_id)


def temperature_unit(block_info: dict[str, Any]) -> str:
    """Detect temperature unit."""
    if block_info[BLOCK_VALUE_UNIT] == "F":
        return TEMP_FAHRENHEIT
    return TEMP_CELSIUS


def get_block_device_name(device: BlockDevice) -> str:
    """Naming for device."""
    return cast(str, device.settings["name"] or device.settings["device"]["hostname"])


def get_rpc_device_name(device: RpcDevice) -> str:
    """Naming for device."""
    # Gen2 does not support setting device name
    # AP SSID name is used as a nicely formatted device name
    return cast(str, device.config["wifi"]["ap"]["ssid"] or device.hostname)


def get_number_of_channels(device: BlockDevice, block: Block) -> int:
    """Get number of channels for block type."""
    assert isinstance(device.shelly, dict)

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

    return channels or 1


def get_block_entity_name(
    device: BlockDevice,
    block: Block | None,
    description: str | None = None,
) -> str:
    """Naming for block based switch and sensors."""
    channel_name = get_block_channel_name(device, block)

    if description:
        return f"{channel_name} {description}"

    return channel_name


def get_block_channel_name(device: BlockDevice, block: Block | None) -> str:
    """Get name based on device and channel name."""
    entity_name = get_block_device_name(device)

    if (
        not block
        or block.type == "device"
        or get_number_of_channels(device, block) == 1
    ):
        return entity_name

    assert block.channel

    channel_name: str | None = None
    mode = cast(str, block.type) + "s"
    if mode in device.settings:
        channel_name = device.settings[mode][int(block.channel)].get("name")

    if channel_name:
        return channel_name

    if device.settings["device"]["type"] == "SHEM-3":
        base = ord("A")
    else:
        base = ord("1")

    return f"{entity_name} channel {chr(int(block.channel)+base)}"


def is_block_momentary_input(settings: dict[str, Any], block: Block) -> bool:
    """Return true if block input button settings is set to a momentary type."""
    # Shelly Button type is fixed to momentary and no btn_type
    if settings["device"]["type"] in SHBTN_MODELS:
        return True

    button = settings.get("relays") or settings.get("lights") or settings.get("inputs")
    if button is None:
        return False

    # Shelly 1L has two button settings in the first channel
    if settings["device"]["type"] == "SHSW-L":
        channel = int(block.channel or 0) + 1
        button_type = button[0].get("btn" + str(channel) + "_type")
    else:
        # Some devices has only one channel in settings
        channel = min(int(block.channel or 0), len(button) - 1)
        button_type = button[channel].get("btn_type")

    return button_type in ["momentary", "momentary_on_release"]


def get_device_uptime(uptime: float, last_uptime: str | None) -> str:
    """Return device uptime string, tolerate up to 5 seconds deviation."""
    delta_uptime = utcnow() - timedelta(seconds=uptime)

    if (
        not last_uptime
        or abs((delta_uptime - datetime.fromisoformat(last_uptime)).total_seconds())
        > UPTIME_DEVIATION
    ):
        return delta_uptime.replace(microsecond=0).isoformat()

    return last_uptime


def get_block_input_triggers(
    device: BlockDevice, block: Block
) -> list[tuple[str, str]]:
    """Return list of input triggers for block."""
    if "inputEvent" not in block.sensor_ids or "inputEventCnt" not in block.sensor_ids:
        return []

    if not is_block_momentary_input(device.settings, block):
        return []

    triggers = []

    if block.type == "device" or get_number_of_channels(device, block) == 1:
        subtype = "button"
    else:
        assert block.channel
        subtype = f"button{int(block.channel)+1}"

    if device.settings["device"]["type"] in SHBTN_MODELS:
        trigger_types = SHBTN_INPUTS_EVENTS_TYPES
    elif device.settings["device"]["type"] == "SHIX3-1":
        trigger_types = SHIX3_1_INPUTS_EVENTS_TYPES
    else:
        trigger_types = BASIC_INPUTS_EVENTS_TYPES

    for trigger_type in trigger_types:
        triggers.append((trigger_type, subtype))

    return triggers


def get_shbtn_input_triggers() -> list[tuple[str, str]]:
    """Return list of input triggers for SHBTN models."""
    triggers = []

    for trigger_type in SHBTN_INPUTS_EVENTS_TYPES:
        triggers.append((trigger_type, "button"))

    return triggers


@singleton.singleton("shelly_coap")
async def get_coap_context(hass: HomeAssistant) -> COAP:
    """Get CoAP context to be used in all Shelly devices."""
    context = COAP()
    if DOMAIN in hass.data:
        port = hass.data[DOMAIN].get(CONF_COAP_PORT, DEFAULT_COAP_PORT)
    else:
        port = DEFAULT_COAP_PORT
    _LOGGER.info("Starting CoAP context with UDP port %s", port)
    await context.initialize(port)

    @callback
    def shutdown_listener(ev: EventType) -> None:
        context.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_listener)

    return context


def get_block_device_sleep_period(settings: dict[str, Any]) -> int:
    """Return the device sleep period in seconds or 0 for non sleeping devices."""
    sleep_period = 0

    if settings.get("sleep_mode", False):
        sleep_period = settings["sleep_mode"]["period"]
        if settings["sleep_mode"]["unit"] == "h":
            sleep_period *= 60  # hours to minutes

    return sleep_period * 60  # minutes to seconds


def get_info_auth(info: dict[str, Any]) -> bool:
    """Return true if device has authorization enabled."""
    return cast(bool, info.get("auth") or info.get("auth_en"))


def get_info_gen(info: dict[str, Any]) -> int:
    """Return the device generation from shelly info."""
    return int(info.get("gen", 1))


def get_model_name(info: dict[str, Any]) -> str:
    """Return the device model name."""
    if get_info_gen(info) == 2:
        return cast(str, MODEL_NAMES.get(info["model"], info["model"]))

    return cast(str, MODEL_NAMES.get(info["type"], info["type"]))


def get_rpc_channel_name(device: RpcDevice, key: str) -> str:
    """Get name based on device and channel name."""
    key = key.replace("input", "switch")
    device_name = get_rpc_device_name(device)
    entity_name: str | None = device.config[key].get("name", device_name)

    if entity_name is None:
        return f"{device_name} {key.replace(':', '_')}"

    return entity_name


def get_rpc_entity_name(
    device: RpcDevice, key: str, description: str | None = None
) -> str:
    """Naming for RPC based switch and sensors."""
    channel_name = get_rpc_channel_name(device, key)

    if description:
        return f"{channel_name} {description}"

    return channel_name


def get_device_entry_gen(entry: ConfigEntry) -> int:
    """Return the device generation from config entry."""
    return entry.data.get("gen", 1)


def get_rpc_key_instances(keys_dict: dict[str, Any], key: str) -> list[str]:
    """Return list of key instances for RPC device from a dict."""
    if key in keys_dict:
        return [key]

    keys_list: list[str] = []
    for i in range(MAX_RPC_KEY_INSTANCES):
        key_inst = f"{key}:{i}"
        if key_inst not in keys_dict:
            return keys_list

        keys_list.append(key_inst)

    return keys_list


def get_rpc_key_ids(keys_dict: dict[str, Any], key: str) -> list[int]:
    """Return list of key ids for RPC device from a dict."""
    key_ids: list[int] = []
    for i in range(MAX_RPC_KEY_INSTANCES):
        key_inst = f"{key}:{i}"
        if key_inst not in keys_dict:
            return key_ids

        key_ids.append(i)

    return key_ids


def is_rpc_momentary_input(config: dict[str, Any], key: str) -> bool:
    """Return true if rpc input button settings is set to a momentary type."""
    return cast(bool, config[key]["type"] == "button")


def is_block_channel_type_light(settings: dict[str, Any], channel: int) -> bool:
    """Return true if block channel appliance type is set to light."""
    app_type = settings["relays"][channel].get("appliance_type")
    return app_type is not None and app_type.lower().startswith("light")


def is_rpc_channel_type_light(config: dict[str, Any], channel: int) -> bool:
    """Return true if rpc channel consumption type is set to light."""
    con_types = config["sys"]["ui_data"].get("consumption_types")
    return con_types is not None and con_types[channel].lower().startswith("light")


def get_rpc_input_triggers(device: RpcDevice) -> list[tuple[str, str]]:
    """Return list of input triggers for RPC device."""
    triggers = []

    key_ids = get_rpc_key_ids(device.config, "input")

    for id_ in key_ids:
        key = f"input:{id_}"
        if not is_rpc_momentary_input(device.config, key):
            continue

        for trigger_type in RPC_INPUTS_EVENTS_TYPES:
            subtype = f"button{id_+1}"
            triggers.append((trigger_type, subtype))

    return triggers
