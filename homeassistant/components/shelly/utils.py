"""Shelly helpers functions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import TYPE_CHECKING, Any, cast

from aiohttp.web import Request, WebSocketResponse
from aioshelly.block_device import COAP, Block, BlockDevice
from aioshelly.const import (
    BLOCK_GENERATIONS,
    BLU_TRV_IDENTIFIER,
    BLU_TRV_MODEL_NAME,
    DEFAULT_COAP_PORT,
    DEFAULT_HTTP_PORT,
    MODEL_1L,
    MODEL_BLU_GATEWAY_G3,
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
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
    singleton,
)
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util.dt import utcnow

from .const import (
    API_WS_URL,
    BASIC_INPUTS_EVENTS_TYPES,
    COMPONENT_ID_PATTERN,
    CONF_COAP_PORT,
    CONF_GEN,
    DEVICE_UNIT_MAP,
    DEVICES_WITHOUT_FIRMWARE_CHANGELOG,
    DOMAIN,
    FIRMWARE_UNSUPPORTED_ISSUE_ID,
    GEN1_RELEASE_URL,
    GEN2_BETA_RELEASE_URL,
    GEN2_RELEASE_URL,
    LOGGER,
    MAX_SCRIPT_SIZE,
    ROLE_GENERIC,
    RPC_INPUTS_EVENTS_TYPES,
    SHAIR_MAX_WORK_HOURS,
    SHBTN_INPUTS_EVENTS_TYPES,
    SHBTN_MODELS,
    SHELLY_EMIT_EVENT_PATTERN,
    SHIX3_1_INPUTS_EVENTS_TYPES,
    UPTIME_DEVIATION,
    VIRTUAL_COMPONENTS,
    VIRTUAL_COMPONENTS_MAP,
    All_LIGHT_TYPES,
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


def get_block_number_of_channels(device: BlockDevice, block: Block) -> int:
    """Get number of channels."""
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

    return channels or 1


def get_block_custom_name(device: BlockDevice, block: Block | None) -> str | None:
    """Get custom name from device settings."""
    if block and (key := cast(str, block.type) + "s") and key in device.settings:
        assert block.channel

        if name := device.settings[key][int(block.channel)].get("name"):
            return cast(str, name)

    return None


def get_block_channel(block: Block | None, base: str = "1") -> str:
    """Get block channel."""
    assert block and block.channel

    return chr(int(block.channel) + ord(base))


def get_block_sub_device_name(device: BlockDevice, block: Block) -> str:
    """Get name of block sub-device."""
    if TYPE_CHECKING:
        assert block.channel

    if custom_name := get_block_custom_name(device, block):
        return custom_name

    if device.settings["device"]["type"] == MODEL_EM3:
        return f"{device.name} Phase {get_block_channel(block, 'A')}"

    return f"{device.name} Channel {get_block_channel(block)}"


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


def is_block_exclude_from_relay(settings: dict[str, Any], block: Block) -> bool:
    """Return true if block should be excluded from switch platform."""

    if settings.get("mode") == "roller":
        return True

    return is_block_channel_type_light(settings, block)


def get_device_uptime(uptime: float, last_uptime: datetime | None) -> datetime:
    """Return device uptime string, tolerate up to 5 seconds deviation."""
    delta_uptime = utcnow() - timedelta(seconds=uptime)

    if (
        not last_uptime
        or (diff := abs((delta_uptime - last_uptime).total_seconds()))
        > UPTIME_DEVIATION
    ):
        if last_uptime:
            LOGGER.debug(
                "Time deviation %s > %s: uptime=%s, last_uptime=%s, delta_uptime=%s",
                diff,
                UPTIME_DEVIATION,
                uptime,
                last_uptime,
                delta_uptime,
            )
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

    if block.type == "device" or get_block_number_of_channels(device, block) == 1:
        subtype = "button"
    else:
        assert block.channel
        subtype = f"button{int(block.channel) + 1}"

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
        return cast(str, MODEL_NAMES.get(info[CONF_MODEL], info[CONF_MODEL]))

    return cast(str, MODEL_NAMES.get(info["type"], info["type"]))


def get_shelly_model_name(
    model: str,
    sleep_period: int,
    device: BlockDevice | RpcDevice,
) -> str | None:
    """Get Shelly model name.

    Assume that XMOD devices are not sleepy devices.
    """
    if (
        sleep_period == 0
        and isinstance(device, RpcDevice)
        and (model_name := device.xmod_info.get("n"))
    ):
        # Use the model name from XMOD data
        return cast(str, model_name)

    # Use the model name from aioshelly
    return cast(str, MODEL_NAMES.get(model))


def get_rpc_key(value: str) -> tuple[bool, str, str]:
    """Get split device key."""
    parts = value.split(":")
    return len(parts) > 1, parts[0], parts[-1]


def get_rpc_key_id(value: str) -> int:
    """Get id from device key."""
    return int(get_rpc_key(value)[-1])


def get_rpc_custom_name(device: RpcDevice, key: str) -> str | None:
    """Get custom name from device config."""
    if (
        key in device.config
        and key != "em:0"  # workaround for Pro 3EM, we don't want to get name for em:0
        and (name := device.config[key].get("name"))
    ):
        return cast(str, name)

    return None


def get_rpc_number_of_channels(device: RpcDevice, component: str) -> int:
    """Get number of channels."""
    return len(get_rpc_key_instances(device.status, component, all_lights=True))


def get_rpc_channel_name(device: RpcDevice, key: str) -> str | None:
    """Get name based on device and channel name."""
    if BLU_TRV_IDENTIFIER in key:
        return None

    _, component, component_id = get_rpc_key(key)

    if custom_name := get_rpc_custom_name(device, key):
        if component in (*VIRTUAL_COMPONENTS, "input", "presencezone", "script"):
            return custom_name

        return (
            custom_name if get_rpc_number_of_channels(device, component) == 1 else None
        )

    if component in (*VIRTUAL_COMPONENTS, "input"):
        return f"{component.title()} {component_id}"

    return None


def get_rpc_key_normalized(key: str) -> str:
    """Get normalized key. Workaround for Pro EM50 and Pro 3EM."""
    # workaround for Pro EM50
    key = key.replace("em1data", "em1")
    # workaround for Pro 3EM
    return key.replace("emdata", "em")


def get_rpc_sub_device_name(
    device: RpcDevice, key: str, emeter_phase: str | None = None
) -> str:
    """Get name based on device and channel name."""
    if key in device.config and key != "em:0":
        # workaround for Pro 3EM, we don't want to get name for em:0
        if (zone_id := get_irrigation_zone_id(device, key)) is not None:
            # workaround for Irrigation controller, name stored in "service:0"
            if zone_name := device.config["service:0"]["zones"][zone_id]["name"]:
                return cast(str, zone_name)

        if entity_name := device.config[key].get("name"):
            return cast(str, entity_name)

    _, component, component_id = get_rpc_key(get_rpc_key_normalized(key))

    if component in ("cct", "rgb", "rgbw"):
        return f"{device.name} {component.upper()} light {component_id}"
    if component == "em1":
        return f"{device.name} Energy Meter {component_id}"
    if component == "em" and emeter_phase is not None:
        return f"{device.name} Phase {emeter_phase}"
    if component == "switch":
        return f"{device.name} Output {component_id}"

    return f"{device.name} {component.title()} {component_id}"


def get_device_entry_gen(entry: ConfigEntry) -> int:
    """Return the device generation from config entry."""
    return entry.data.get(CONF_GEN, 1)  # type: ignore[no-any-return]


def get_rpc_key_instances(
    keys_dict: dict[str, Any], key: str, all_lights: bool = False
) -> list[str]:
    """Return list of key instances for RPC device from a dict."""
    if key in keys_dict:
        return [key]

    if key == "switch" and "cover:0" in keys_dict:
        key = "cover"

    if key in All_LIGHT_TYPES and all_lights:
        return [k for k in keys_dict if k.startswith(All_LIGHT_TYPES)]

    return [k for k in keys_dict if k.startswith(f"{key}:")]


def get_rpc_key_ids(keys_dict: dict[str, Any], key: str) -> list[int]:
    """Return list of key ids for RPC device from a dict."""
    return [get_rpc_key_id(k) for k in keys_dict if k.startswith(f"{key}:")]


def get_rpc_key_by_role(keys_dict: dict[str, Any], role: str) -> str | None:
    """Return key by role for RPC device from a dict."""
    for key, value in keys_dict.items():
        if value.get("role") == role:
            return key
    return None


def get_rpc_role_by_key(keys_dict: dict[str, Any], key: str) -> str:
    """Return role by key for RPC device from a dict."""
    return cast(str, keys_dict[key].get("role", ROLE_GENERIC))


def is_rpc_momentary_input(
    config: dict[str, Any], status: dict[str, Any], key: str
) -> bool:
    """Return true if rpc input button settings is set to a momentary type."""
    return cast(bool, config[key]["type"] == "button")


def is_block_channel_type_light(settings: dict[str, Any], block: Block) -> bool:
    """Return true if block channel appliance type is set to light."""
    if TYPE_CHECKING:
        assert block.channel is not None

    app_type = settings["relays"][int(block.channel)].get("appliance_type")
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
            subtype = f"button{id_ + 1}"
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
    base = name.split(".", 1)[0]
    if "-" not in base:
        return None

    mac = base.rsplit("-", 1)[-1]
    if len(mac) != 12 or not all(char in "0123456789abcdefABCDEF" for char in mac):
        return None

    return mac.upper()


def get_release_url(gen: int, model: str, beta: bool) -> str | None:
    """Return release URL or None."""
    if (
        beta and gen in BLOCK_GENERATIONS
    ) or model in DEVICES_WITHOUT_FIRMWARE_CHANGELOG:
        return None

    if beta:
        return GEN2_BETA_RELEASE_URL

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
            "ip_address": entry.data[CONF_HOST],
        },
    )


def is_rpc_wifi_stations_disabled(
    config: dict[str, Any], _status: dict[str, Any], key: str
) -> bool:
    """Return true if rpc all WiFi stations are disabled."""
    if config[key]["sta"]["enable"] is True or config[key]["sta1"]["enable"] is True:
        return False

    return True


def get_http_port(data: Mapping[str, Any]) -> int:
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


def get_virtual_component_ids(config: dict[str, Any], platform: str) -> list[str]:
    """Return a list of virtual component IDs for a platform."""
    component = VIRTUAL_COMPONENTS_MAP[platform]

    ids: list[str] = []

    for comp_type in component["types"]:
        ids.extend(
            k
            for k, v in config.items()
            if k.startswith(comp_type)
            # default to button view if not set, workaround for Wall Display
            and v.get("meta", {"ui": {"view": "button"}})["ui"]["view"]
            in component["modes"]
        )

    return ids


def is_view_for_platform(config: dict[str, Any], key: str, platform: str) -> bool:
    """Return true if the virtual component view match the platform."""
    component = VIRTUAL_COMPONENTS_MAP[platform]
    view = config[key]["meta"]["ui"]["view"]
    return view in component["modes"]


def get_virtual_component_unit(config: dict[str, Any]) -> str | None:
    """Return the unit of a virtual component.

    If the unit is not set, the device sends an empty string
    """
    unit = config["meta"]["ui"]["unit"]
    return DEVICE_UNIT_MAP.get(unit, unit) if unit else None


@callback
def async_remove_orphaned_entities(
    hass: HomeAssistant,
    config_entry_id: str,
    mac: str,
    platform: str,
    keys: Iterable[str],
    key_suffix: str | None = None,
) -> None:
    """Remove orphaned entities."""
    orphaned_entities = []
    entity_reg = er.async_get(hass)

    entities = er.async_entries_for_config_entry(entity_reg, config_entry_id)
    for entity in entities:
        if not entity.entity_id.startswith(platform):
            continue
        if key_suffix is not None and key_suffix not in entity.unique_id:
            continue
        # we are looking for the component ID, e.g. boolean:201, em1data:1
        if not (match := COMPONENT_ID_PATTERN.search(entity.unique_id)):
            continue

        key = match.group()
        if key not in keys:
            LOGGER.debug(
                "Found orphaned Shelly entity: %s, unique id: %s",
                entity.entity_id,
                entity.unique_id,
            )
            orphaned_entities.append(entity.unique_id.split("-", 1)[1])

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


async def get_rpc_script_event_types(device: RpcDevice, id: int) -> list[str]:
    """Return a list of event types for a specific script."""
    code_response = await device.script_getcode(id, bytes_to_read=MAX_SCRIPT_SIZE)
    matches = SHELLY_EMIT_EVENT_PATTERN.finditer(code_response["data"])
    return sorted([*{str(event_type.group(1)) for event_type in matches}])


def is_rpc_exclude_from_relay(
    settings: dict[str, Any], status: dict[str, Any], channel: str
) -> bool:
    """Return true if rpc channel should be excludeed from switch platform."""
    if is_rpc_thermostat_internal_actuator(status):
        return True

    return is_rpc_channel_type_light(settings, get_rpc_key_id(channel))


def get_shelly_air_lamp_life(lamp_seconds: int) -> float:
    """Return Shelly Air lamp life in percentage."""
    lamp_hours = lamp_seconds / 3600
    if lamp_hours >= SHAIR_MAX_WORK_HOURS:
        return 0.0
    return 100 * (1 - lamp_hours / SHAIR_MAX_WORK_HOURS)


async def get_rpc_scripts_event_types(
    device: RpcDevice, ignore_scripts: list[str]
) -> dict[int, list[str]]:
    """Return a dict of all scripts and their event types."""
    script_events = {}
    for script in get_rpc_key_instances(device.status, "script"):
        if get_rpc_channel_name(device, script) in ignore_scripts:
            continue

        script_id = get_rpc_key_id(script)
        script_events[script_id] = await get_rpc_script_event_types(device, script_id)

    return script_events


def get_irrigation_zone_id(device: RpcDevice, key: str) -> int | None:
    """Return the zone id if the component is an irrigation zone."""
    if (
        device.initialized
        and key in device.config
        and (zone := get_rpc_role_by_key(device.config, key)).startswith("zone")
    ):
        return int(zone[4:])
    return None


def get_rpc_device_info(
    device: RpcDevice,
    mac: str,
    configuration_url: str,
    model: str,
    model_name: str | None = None,
    key: str | None = None,
    emeter_phase: str | None = None,
    suggested_area: str | None = None,
) -> DeviceInfo:
    """Return device info for RPC device."""
    if key is None:
        return DeviceInfo(connections={(CONNECTION_NETWORK_MAC, mac)})

    key = get_rpc_key_normalized(key)
    has_id, component, _ = get_rpc_key(key)

    if emeter_phase is not None:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{mac}-{key}-{emeter_phase.lower()}")},
            name=get_rpc_sub_device_name(device, key, emeter_phase),
            manufacturer="Shelly",
            model=model_name,
            model_id=model,
            suggested_area=suggested_area,
            via_device=(DOMAIN, mac),
            configuration_url=configuration_url,
        )

    if (
        (
            component not in (*All_LIGHT_TYPES, "cover", "em1", "switch")
            and get_irrigation_zone_id(device, key) is None
        )
        or not has_id
        or get_rpc_number_of_channels(device, component) < 2
    ):
        return DeviceInfo(connections={(CONNECTION_NETWORK_MAC, mac)})

    return DeviceInfo(
        identifiers={(DOMAIN, f"{mac}-{key}")},
        name=get_rpc_sub_device_name(device, key),
        manufacturer="Shelly",
        model=model_name,
        model_id=model,
        suggested_area=suggested_area,
        via_device=(DOMAIN, mac),
        configuration_url=configuration_url,
    )


def get_blu_trv_device_info(
    config: dict[str, Any], ble_addr: str, parent_mac: str, fw_ver: str | None
) -> DeviceInfo:
    """Return device info for RPC device."""
    model_id = config.get("local_name")
    return DeviceInfo(
        connections={(CONNECTION_BLUETOOTH, ble_addr)},
        identifiers={(DOMAIN, ble_addr)},
        via_device=(DOMAIN, parent_mac),
        manufacturer="Shelly",
        model=BLU_TRV_MODEL_NAME.get(model_id) if model_id else None,
        model_id=config.get("local_name"),
        name=config["name"] or f"shellyblutrv-{ble_addr.replace(':', '')}",
        sw_version=fw_ver,
    )


def is_block_single_device(device: BlockDevice, block: Block | None = None) -> bool:
    """Return true if block is single device."""
    return (
        block is None
        or block.type not in ("light", "relay", "emeter")
        or device.settings.get("mode") == "roller"
    )


def get_block_device_info(
    device: BlockDevice,
    mac: str,
    configuration_url: str,
    model: str,
    model_name: str | None = None,
    block: Block | None = None,
    suggested_area: str | None = None,
) -> DeviceInfo:
    """Return device info for Block device."""
    if is_block_single_device(device, block) or (
        block is not None and get_block_number_of_channels(device, block) < 2
    ):
        return DeviceInfo(connections={(CONNECTION_NETWORK_MAC, mac)})

    if TYPE_CHECKING:
        assert block

    return DeviceInfo(
        identifiers={(DOMAIN, f"{mac}-{block.description}")},
        name=get_block_sub_device_name(device, block),
        manufacturer="Shelly",
        model=model_name,
        model_id=model,
        suggested_area=suggested_area,
        via_device=(DOMAIN, mac),
        configuration_url=configuration_url,
    )


@callback
def remove_stale_blu_trv_devices(
    hass: HomeAssistant, rpc_device: RpcDevice, entry: ConfigEntry
) -> None:
    """Remove stale BLU TRV devices."""
    if rpc_device.model != MODEL_BLU_GATEWAY_G3:
        return

    dev_reg = dr.async_get(hass)
    devices = dev_reg.devices.get_devices_for_config_entry_id(entry.entry_id)
    config = rpc_device.config
    blutrv_keys = get_rpc_key_ids(config, BLU_TRV_IDENTIFIER)
    trv_addrs = [config[f"{BLU_TRV_IDENTIFIER}:{key}"]["addr"] for key in blutrv_keys]

    for device in devices:
        if not device.via_device_id:
            # Device is not a sub-device, skip
            continue

        if any(
            identifier[0] == DOMAIN and identifier[1] in trv_addrs
            for identifier in device.identifiers
        ):
            continue

        LOGGER.debug("Removing stale BLU TRV device %s", device.name)
        dev_reg.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


@callback
def remove_empty_sub_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove sub devices without entities."""
    dev_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    devices = dev_reg.devices.get_devices_for_config_entry_id(entry.entry_id)

    for device in devices:
        if not device.via_device_id:
            # Device is not a sub-device, skip
            continue

        if er.async_entries_for_device(entity_reg, device.id, True):
            # Device has entities, skip
            continue

        if any(identifier[0] == DOMAIN for identifier in device.identifiers):
            LOGGER.debug("Removing empty sub-device %s", device.name)
            dev_reg.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )


def format_ble_addr(ble_addr: str) -> str:
    """Format BLE address to use in unique_id."""
    return ble_addr.replace(":", "").upper()


@callback
def async_migrate_rpc_virtual_components_unique_ids(
    config: dict[str, Any], entity_entry: er.RegistryEntry
) -> dict[str, Any] | None:
    """Migrate RPC virtual components unique_ids to include role in the ID.

    This is needed to support multiple components with the same key.
    The old unique_id format is: {mac}-{key}-{component}
    The new unique_id format is: {mac}-{key}-{component}_{role}
    """
    for component in VIRTUAL_COMPONENTS:
        if (
            entity_entry.unique_id.endswith(f"-{component!s}")
            and (key := entity_entry.unique_id.split("-")[-2]) in config
        ):
            role = get_rpc_role_by_key(config, key)
            new_unique_id = f"{entity_entry.unique_id}_{role}"
            LOGGER.debug(
                "Migrating unique_id for %s entity from [%s] to [%s]",
                entity_entry.entity_id,
                entity_entry.unique_id,
                new_unique_id,
            )
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    entity_entry.unique_id, new_unique_id
                )
            }

    return None


def is_rpc_ble_scanner_supported(entry: ConfigEntry) -> bool:
    """Return true if BLE scanner is supported."""
    return (
        entry.runtime_data.rpc_supports_scripts
        and not entry.runtime_data.rpc_zigbee_firmware
    )
