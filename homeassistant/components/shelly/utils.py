"""Shelly helpers functions."""

from __future__ import annotations

from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv6Address, ip_address
import re
from types import MappingProxyType
from typing import Any, cast

from aiohttp.web import Request, WebSocketResponse
from aioshelly.block_device import COAP, Block, BlockDevice
from aioshelly.const import (
    BLOCK_GENERATIONS,
    DEFAULT_COAP_PORT,
    DEFAULT_HTTP_PORT,
    MODEL_1L,
    MODEL_DIMMER,
    MODEL_DIMMER_2,
    MODEL_EM3,
    MODEL_I3,
    MODEL_NAMES,
    RPC_GENERATIONS,
)
from aioshelly.rpc_device import RpcDevice, WsServer
from yarl import URL

from homeassistant.components import network
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
    singleton,
)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util.dt import utcnow

from .const import (
    API_WS_URL,
    BASIC_INPUTS_EVENTS_TYPES,
    CONF_COAP_PORT,
    CONF_GEN,
    DEVICES_WITHOUT_FIRMWARE_CHANGELOG,
    DOMAIN,
    FIRMWARE_UNSUPPORTED_ISSUE_ID,
    GEN1_RELEASE_URL,
    GEN2_RELEASE_URL,
    LOGGER,
    RPC_INPUTS_EVENTS_TYPES,
    SHBTN_INPUTS_EVENTS_TYPES,
    SHBTN_MODELS,
    SHIX3_1_INPUTS_EVENTS_TYPES,
    UPTIME_DEVIATION,
    VIRTUAL_COMPONENTS_MAP,
)


@callback
def async_remove_shelly_entity(
    hass: HomeAssistant, domain: str, unique_id: str
) -> None:
    """Remove a Shelly entity."""
    entity_reg = er.async_get(hass)
    entity_id = entity_reg.async_get_entity_id(domain, DOMAIN, unique_id)
    if entity_id:
        LOGGER.debug("Removing entity: %s", entity_id)
        entity_reg.async_remove(entity_id)


def get_number_of_channels(device: BlockDevice, block: Block) -> int:
    """Get number of channels for block type."""
    channels = None

    if block.type == "input":
        # Shelly Dimmer/1L has two input channels and missing "num_inputs"
        if device.settings["device"]["type"] in [
            MODEL_DIMMER,
            MODEL_DIMMER_2,
            MODEL_1L,
        ]:
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
        return f"{channel_name} {description.lower()}"

    return channel_name


def get_block_channel_name(device: BlockDevice, block: Block | None) -> str:
    """Get name based on device and channel name."""
    entity_name = device.name

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

    if device.settings["device"]["type"] == MODEL_EM3:
        base = ord("A")
    else:
        base = ord("1")

    return f"{entity_name} channel {chr(int(block.channel)+base)}"


def is_block_momentary_input(
    settings: dict[str, Any], block: Block, include_detached: bool = False
) -> bool:
    """Return true if block input button settings is set to a momentary type."""
    momentary_types = ["momentary", "momentary_on_release"]

    if include_detached:
        momentary_types.append("detached")

    # Shelly Button type is fixed to momentary and no btn_type
    if settings["device"]["type"] in SHBTN_MODELS:
        return True

    if settings.get("mode") == "roller":
        button_type = settings["rollers"][0]["button_type"]
        return button_type in momentary_types

    button = settings.get("relays") or settings.get("lights") or settings.get("inputs")
    if button is None:
        return False

    # Shelly 1L has two button settings in the first channel
    if settings["device"]["type"] == MODEL_1L:
        channel = int(block.channel or 0) + 1
        button_type = button[0].get("btn" + str(channel) + "_type")
    else:
        # Some devices has only one channel in settings
        channel = min(int(block.channel or 0), len(button) - 1)
        button_type = button[channel].get("btn_type")

    return button_type in momentary_types


def get_device_uptime(uptime: float, last_uptime: datetime | None) -> datetime:
    """Return device uptime string, tolerate up to 5 seconds deviation."""
    delta_uptime = utcnow() - timedelta(seconds=uptime)

    if (
        not last_uptime
        or abs((delta_uptime - last_uptime).total_seconds()) > UPTIME_DEVIATION
    ):
        return delta_uptime

    return last_uptime


def get_block_input_triggers(
    device: BlockDevice, block: Block
) -> list[tuple[str, str]]:
    """Return list of input triggers for block."""
    if "inputEvent" not in block.sensor_ids or "inputEventCnt" not in block.sensor_ids:
        return []

    if not is_block_momentary_input(device.settings, block, True):
        return []

    if block.type == "device" or get_number_of_channels(device, block) == 1:
        subtype = "button"
    else:
        assert block.channel
        subtype = f"button{int(block.channel)+1}"

    if device.settings["device"]["type"] in SHBTN_MODELS:
        trigger_types = SHBTN_INPUTS_EVENTS_TYPES
    elif device.settings["device"]["type"] == MODEL_I3:
        trigger_types = SHIX3_1_INPUTS_EVENTS_TYPES
    else:
        trigger_types = BASIC_INPUTS_EVENTS_TYPES

    return [(trigger_type, subtype) for trigger_type in trigger_types]


def get_shbtn_input_triggers() -> list[tuple[str, str]]:
    """Return list of input triggers for SHBTN models."""
    return [(trigger_type, "button") for trigger_type in SHBTN_INPUTS_EVENTS_TYPES]


@singleton.singleton("shelly_coap")
async def get_coap_context(hass: HomeAssistant) -> COAP:
    """Get CoAP context to be used in all Shelly Gen1 devices."""
    context = COAP()

    adapters = await network.async_get_adapters(hass)
    LOGGER.debug("Network adapters: %s", adapters)

    ipv4: list[IPv4Address] = []
    if not network.async_only_default_interface_enabled(adapters):
        ipv4.extend(
            address
            for address in await network.async_get_enabled_source_ips(hass)
            if address.version == 4
            and not (
                address.is_link_local
                or address.is_loopback
                or address.is_multicast
                or address.is_unspecified
            )
        )
    LOGGER.debug("Network IPv4 addresses: %s", ipv4)
    if DOMAIN in hass.data:
        port = hass.data[DOMAIN].get(CONF_COAP_PORT, DEFAULT_COAP_PORT)
    else:
        port = DEFAULT_COAP_PORT
    LOGGER.info("Starting CoAP context with UDP port %s", port)
    await context.initialize(port, ipv4)

    @callback
    def shutdown_listener(ev: Event) -> None:
        context.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_listener)
    return context


class ShellyReceiver(HomeAssistantView):
    """Handle pushes from Shelly Gen2 devices."""

    requires_auth = False
    url = API_WS_URL
    name = "api:shelly:ws"

    def __init__(self, ws_server: WsServer) -> None:
        """Initialize the Shelly receiver view."""
        self._ws_server = ws_server

    async def get(self, request: Request) -> WebSocketResponse:
        """Start a get request."""
        return await self._ws_server.websocket_handler(request)


@singleton.singleton("shelly_ws_server")
async def get_ws_context(hass: HomeAssistant) -> WsServer:
    """Get websocket server context to be used in all Shelly Gen2 devices."""
    ws_server = WsServer()
    hass.http.register_view(ShellyReceiver(ws_server))
    return ws_server


def get_block_device_sleep_period(settings: dict[str, Any]) -> int:
    """Return the device sleep period in seconds or 0 for non sleeping devices."""
    sleep_period = 0

    if settings.get("sleep_mode", False):
        sleep_period = settings["sleep_mode"]["period"]
        if settings["sleep_mode"]["unit"] == "h":
            sleep_period *= 60  # hours to minutes

    return sleep_period * 60  # minutes to seconds


def get_rpc_device_wakeup_period(status: dict[str, Any]) -> int:
    """Return the device wakeup period in seconds or 0 for non sleeping devices."""
    return cast(int, status["sys"].get("wakeup_period", 0))


def get_info_auth(info: dict[str, Any]) -> bool:
    """Return true if device has authorization enabled."""
    return cast(bool, info.get("auth") or info.get("auth_en"))


def get_info_gen(info: dict[str, Any]) -> int:
    """Return the device generation from shelly info."""
    return int(info.get(CONF_GEN, 1))


def get_model_name(info: dict[str, Any]) -> str:
    """Return the device model name."""
    if get_info_gen(info) in RPC_GENERATIONS:
        return cast(str, MODEL_NAMES.get(info["model"], info["model"]))

    return cast(str, MODEL_NAMES.get(info["type"], info["type"]))


def get_rpc_channel_name(device: RpcDevice, key: str) -> str:
    """Get name based on device and channel name."""
    key = key.replace("emdata", "em")
    key = key.replace("em1data", "em1")
    device_name = device.name
    entity_name: str | None = None
    if key in device.config:
        entity_name = device.config[key].get("name", device_name)

    if entity_name is None:
        if key.startswith(("input:", "light:", "switch:")):
            return f"{device_name} {key.replace(':', '_')}"
        if key.startswith("em1"):
            return f"{device_name} EM{key.split(':')[-1]}"
        if key.startswith(("boolean:", "enum:", "number:", "text:")):
            return key.replace(":", " ").title()
        return device_name

    return entity_name


def get_rpc_entity_name(
    device: RpcDevice, key: str, description: str | None = None
) -> str:
    """Naming for RPC based switch and sensors."""
    channel_name = get_rpc_channel_name(device, key)

    if description:
        return f"{channel_name} {description.lower()}"

    return channel_name


def get_device_entry_gen(entry: ConfigEntry) -> int:
    """Return the device generation from config entry."""
    return entry.data.get(CONF_GEN, 1)


def get_rpc_key_instances(keys_dict: dict[str, Any], key: str) -> list[str]:
    """Return list of key instances for RPC device from a dict."""
    if key in keys_dict:
        return [key]

    if key == "switch" and "cover:0" in keys_dict:
        key = "cover"

    return [k for k in keys_dict if k.startswith(f"{key}:")]


def get_rpc_key_ids(keys_dict: dict[str, Any], key: str) -> list[int]:
    """Return list of key ids for RPC device from a dict."""
    return [int(k.split(":")[1]) for k in keys_dict if k.startswith(f"{key}:")]


def is_rpc_momentary_input(
    config: dict[str, Any], status: dict[str, Any], key: str
) -> bool:
    """Return true if rpc input button settings is set to a momentary type."""
    return cast(bool, config[key]["type"] == "button")


def is_block_channel_type_light(settings: dict[str, Any], channel: int) -> bool:
    """Return true if block channel appliance type is set to light."""
    app_type = settings["relays"][channel].get("appliance_type")
    return app_type is not None and app_type.lower().startswith("light")


def is_rpc_channel_type_light(config: dict[str, Any], channel: int) -> bool:
    """Return true if rpc channel consumption type is set to light."""
    con_types = config["sys"].get("ui_data", {}).get("consumption_types")
    if con_types is None or len(con_types) <= channel:
        return False
    return cast(str, con_types[channel]).lower().startswith("light")


def is_rpc_thermostat_internal_actuator(status: dict[str, Any]) -> bool:
    """Return true if the thermostat uses an internal relay."""
    return cast(bool, status["sys"].get("relay_in_thermostat", False))


def get_rpc_input_triggers(device: RpcDevice) -> list[tuple[str, str]]:
    """Return list of input triggers for RPC device."""
    triggers = []

    key_ids = get_rpc_key_ids(device.config, "input")

    for id_ in key_ids:
        key = f"input:{id_}"
        if not is_rpc_momentary_input(device.config, device.status, key):
            continue

        for trigger_type in RPC_INPUTS_EVENTS_TYPES:
            subtype = f"button{id_+1}"
            triggers.append((trigger_type, subtype))

    return triggers


@callback
def update_device_fw_info(
    hass: HomeAssistant, shellydevice: BlockDevice | RpcDevice, entry: ConfigEntry
) -> None:
    """Update the firmware version information in the device registry."""
    assert entry.unique_id

    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)},
        connections={(CONNECTION_NETWORK_MAC, dr.format_mac(entry.unique_id))},
    ):
        if device.sw_version == shellydevice.firmware_version:
            return

        LOGGER.debug("Updating device registry info for %s", entry.title)

        dev_reg.async_update_device(device.id, sw_version=shellydevice.firmware_version)


def brightness_to_percentage(brightness: int) -> int:
    """Convert brightness level to percentage."""
    return int(100 * (brightness + 1) / 255)


def percentage_to_brightness(percentage: int) -> int:
    """Convert percentage to brightness level."""
    return round(255 * percentage / 100)


def mac_address_from_name(name: str) -> str | None:
    """Convert a name to a mac address."""
    mac = name.partition(".")[0].partition("-")[-1]
    return mac.upper() if len(mac) == 12 else None


def get_release_url(gen: int, model: str, beta: bool) -> str | None:
    """Return release URL or None."""
    if beta or model in DEVICES_WITHOUT_FIRMWARE_CHANGELOG:
        return None

    return GEN1_RELEASE_URL if gen in BLOCK_GENERATIONS else GEN2_RELEASE_URL


@callback
def async_create_issue_unsupported_firmware(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Create a repair issue if the device runs an unsupported firmware."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        FIRMWARE_UNSUPPORTED_ISSUE_ID.format(unique=entry.unique_id),
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="unsupported_firmware",
        translation_placeholders={
            "device_name": entry.title,
            "ip_address": entry.data["host"],
        },
    )


def is_rpc_wifi_stations_disabled(
    config: dict[str, Any], _status: dict[str, Any], key: str
) -> bool:
    """Return true if rpc all WiFi stations are disabled."""
    if config[key]["sta"]["enable"] is True or config[key]["sta1"]["enable"] is True:
        return False

    return True


def get_http_port(data: MappingProxyType[str, Any]) -> int:
    """Get port from config entry data."""
    return cast(int, data.get(CONF_PORT, DEFAULT_HTTP_PORT))


def get_host(host: str) -> str:
    """Get the device IP address or hostname."""
    try:
        ip_object = ip_address(host)
    except ValueError:
        # host contains hostname
        return host

    if isinstance(ip_object, IPv6Address):
        return f"[{host}]"

    return host


@callback
def async_remove_shelly_rpc_entities(
    hass: HomeAssistant, domain: str, mac: str, keys: list[str]
) -> None:
    """Remove RPC based Shelly entity."""
    entity_reg = er.async_get(hass)
    for key in keys:
        if entity_id := entity_reg.async_get_entity_id(domain, DOMAIN, f"{mac}-{key}"):
            LOGGER.debug("Removing entity: %s", entity_id)
            entity_reg.async_remove(entity_id)


def is_rpc_thermostat_mode(ident: int, status: dict[str, Any]) -> bool:
    """Return True if 'thermostat:<IDent>' is present in the status."""
    return f"thermostat:{ident}" in status


def get_virtual_component_ids(config: dict[str, Any], platform: str) -> list[str]:
    """Return a list of virtual component IDs for a platform."""
    component = VIRTUAL_COMPONENTS_MAP.get(platform)

    if not component:
        return []

    ids: list[str] = []

    for comp_type in component["types"]:
        ids.extend(
            k
            for k, v in config.items()
            if k.startswith(comp_type) and v["meta"]["ui"]["view"] in component["modes"]
        )

    return ids


@callback
def async_remove_orphaned_virtual_entities(
    hass: HomeAssistant,
    config_entry_id: str,
    mac: str,
    platform: str,
    virt_comp_type: str,
    virt_comp_ids: list[str],
) -> None:
    """Remove orphaned virtual entities."""
    orphaned_entities = []
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    if not (
        devices := device_reg.devices.get_devices_for_config_entry_id(config_entry_id)
    ):
        return

    device_id = devices[0].id
    entities = er.async_entries_for_device(entity_reg, device_id, True)
    for entity in entities:
        if not entity.entity_id.startswith(platform):
            continue
        if virt_comp_type not in entity.unique_id:
            continue
        # we are looking for the component ID, e.g. boolean:201
        if not (match := re.search(r"[a-z]+:\d+", entity.unique_id)):
            continue
        virt_comp_id = match.group()
        if virt_comp_id not in virt_comp_ids:
            orphaned_entities.append(f"{virt_comp_id}-{virt_comp_type}")

    if orphaned_entities:
        async_remove_shelly_rpc_entities(hass, platform, mac, orphaned_entities)


def get_rpc_ws_url(hass: HomeAssistant) -> str | None:
    """Return the RPC websocket URL."""
    try:
        raw_url = get_url(hass, prefer_external=False, allow_cloud=False)
    except NoURLAvailableError:
        LOGGER.debug("URL not available, skipping outbound websocket setup")
        return None
    url = URL(raw_url)
    ws_url = url.with_scheme("wss" if url.scheme == "https" else "ws")
    return str(ws_url.joinpath(API_WS_URL.removeprefix("/")))
