"""Connect to a MySensors gateway via pymysensors API."""
from __future__ import annotations

import asyncio
from functools import partial
import logging
from typing import Callable

from mysensors import BaseAsyncGateway
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.mqtt import valid_publish_topic, valid_subscribe_topic
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_OPTIMISTIC
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DEVICES,
    CONF_BAUD_RATE,
    CONF_DEVICE,
    CONF_GATEWAYS,
    CONF_NODES,
    CONF_PERSISTENCE,
    CONF_PERSISTENCE_FILE,
    CONF_RETAIN,
    CONF_TCP_PORT,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
    CONF_VERSION,
    DOMAIN,
    MYSENSORS_DISCOVERY,
    MYSENSORS_GATEWAYS,
    MYSENSORS_ON_UNLOAD,
    PLATFORMS_WITH_ENTRY_SUPPORT,
    DevId,
    SensorType,
)
from .device import MySensorsDevice, MySensorsEntity, get_mysensors_devices
from .gateway import finish_setup, get_mysensors_gateway, gw_stop, setup_gateway
from .helpers import on_unload

_LOGGER = logging.getLogger(__name__)

CONF_DEBUG = "debug"
CONF_NODE_NAME = "name"

DATA_HASS_CONFIG = "hass_config"

DEFAULT_BAUD_RATE = 115200
DEFAULT_TCP_PORT = 5003
DEFAULT_VERSION = "1.4"


def set_default_persistence_file(value: dict) -> dict:
    """Set default persistence file."""
    for idx, gateway in enumerate(value):
        fil = gateway.get(CONF_PERSISTENCE_FILE)
        if fil is not None:
            continue
        new_name = f"mysensors{idx + 1}.pickle"
        gateway[CONF_PERSISTENCE_FILE] = new_name

    return value


def has_all_unique_files(value):
    """Validate that all persistence files are unique and set if any is set."""
    persistence_files = [gateway[CONF_PERSISTENCE_FILE] for gateway in value]
    schema = vol.Schema(vol.Unique())
    schema(persistence_files)
    return value


def is_persistence_file(value):
    """Validate that persistence file path ends in either .pickle or .json."""
    if value.endswith((".json", ".pickle")):
        return value
    raise vol.Invalid(f"{value} does not end in either `.json` or `.pickle`")


def deprecated(key):
    """Mark key as deprecated in configuration."""

    def validator(config):
        """Check if key is in config, log warning and remove key."""
        if key not in config:
            return config
        _LOGGER.warning(
            "%s option for %s is deprecated. Please remove %s from your "
            "configuration file",
            key,
            DOMAIN,
            key,
        )
        config.pop(key)
        return config

    return validator


NODE_SCHEMA = vol.Schema({cv.positive_int: {vol.Required(CONF_NODE_NAME): cv.string}})

GATEWAY_SCHEMA = vol.Schema(
    vol.All(
        deprecated(CONF_NODES),
        {
            vol.Required(CONF_DEVICE): cv.string,
            vol.Optional(CONF_PERSISTENCE_FILE): vol.All(
                cv.string, is_persistence_file
            ),
            vol.Optional(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE): cv.positive_int,
            vol.Optional(CONF_TCP_PORT, default=DEFAULT_TCP_PORT): cv.port,
            vol.Optional(CONF_TOPIC_IN_PREFIX): valid_subscribe_topic,
            vol.Optional(CONF_TOPIC_OUT_PREFIX): valid_publish_topic,
            vol.Optional(CONF_NODES, default={}): NODE_SCHEMA,
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                deprecated(CONF_DEBUG),
                deprecated(CONF_OPTIMISTIC),
                deprecated(CONF_PERSISTENCE),
                {
                    vol.Required(CONF_GATEWAYS): vol.All(
                        cv.ensure_list,
                        set_default_persistence_file,
                        has_all_unique_files,
                        [GATEWAY_SCHEMA],
                    ),
                    vol.Optional(CONF_RETAIN, default=True): cv.boolean,
                    vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): cv.string,
                    vol.Optional(CONF_OPTIMISTIC, default=False): cv.boolean,
                    vol.Optional(CONF_PERSISTENCE, default=True): cv.boolean,
                },
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the MySensors component."""
    hass.data[DOMAIN] = {DATA_HASS_CONFIG: config}

    if DOMAIN not in config or bool(hass.config_entries.async_entries(DOMAIN)):
        return True

    config = config[DOMAIN]
    user_inputs = [
        {
            CONF_DEVICE: gw[CONF_DEVICE],
            CONF_BAUD_RATE: gw[CONF_BAUD_RATE],
            CONF_TCP_PORT: gw[CONF_TCP_PORT],
            CONF_TOPIC_OUT_PREFIX: gw.get(CONF_TOPIC_OUT_PREFIX, ""),
            CONF_TOPIC_IN_PREFIX: gw.get(CONF_TOPIC_IN_PREFIX, ""),
            CONF_RETAIN: config[CONF_RETAIN],
            CONF_VERSION: config[CONF_VERSION],
            CONF_PERSISTENCE_FILE: gw[CONF_PERSISTENCE_FILE]
            # nodes config ignored at this time. renaming nodes can now be done from the frontend.
        }
        for gw in config[CONF_GATEWAYS]
    ]
    user_inputs = [
        {k: v for k, v in userinput.items() if v is not None}
        for userinput in user_inputs
    ]

    # there is an actual configuration in configuration.yaml, so we have to process it
    for user_input in user_inputs:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=user_input,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an instance of the MySensors integration.

    Every instance has a connection to exactly one Gateway.
    """
    gateway = await setup_gateway(hass, entry)

    if not gateway:
        _LOGGER.error("Gateway setup failed for %s", entry.data)
        return False

    if MYSENSORS_GATEWAYS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][MYSENSORS_GATEWAYS] = {}
    hass.data[DOMAIN][MYSENSORS_GATEWAYS][entry.entry_id] = gateway

    # Connect notify discovery as that integration doesn't support entry forwarding.
    # Allow loading device tracker platform via discovery
    # until refactor to config entry is done.

    for platform in (DEVICE_TRACKER_DOMAIN, NOTIFY_DOMAIN):
        load_discovery_platform = partial(
            async_load_platform,
            hass,
            platform,
            DOMAIN,
            hass_config=hass.data[DOMAIN][DATA_HASS_CONFIG],
        )

        await on_unload(
            hass,
            entry.entry_id,
            async_dispatcher_connect(
                hass,
                MYSENSORS_DISCOVERY.format(entry.entry_id, platform),
                load_discovery_platform,
            ),
        )

    async def finish() -> None:
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, platform)
                for platform in PLATFORMS_WITH_ENTRY_SUPPORT
            ]
        )
        await finish_setup(hass, entry, gateway)

    hass.async_create_task(finish())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove an instance of the MySensors integration."""

    gateway = get_mysensors_gateway(hass, entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_WITH_ENTRY_SUPPORT
    )
    if not unload_ok:
        return False

    key = MYSENSORS_ON_UNLOAD.format(entry.entry_id)
    if key in hass.data[DOMAIN]:
        for fnct in hass.data[DOMAIN][key]:
            fnct()

        hass.data[DOMAIN].pop(key)

    del hass.data[DOMAIN][MYSENSORS_GATEWAYS][entry.entry_id]

    await gw_stop(hass, entry, gateway)
    return True


@callback
def setup_mysensors_platform(
    hass: HomeAssistant,
    domain: str,  # hass platform name
    discovery_info: dict[str, list[DevId]],
    device_class: type[MySensorsDevice] | dict[SensorType, type[MySensorsEntity]],
    device_args: (
        None | tuple
    ) = None,  # extra arguments that will be given to the entity constructor
    async_add_entities: Callable | None = None,
) -> list[MySensorsDevice] | None:
    """Set up a MySensors platform.

    Sets up a bunch of instances of a single platform that is supported by this integration.
    The function is given a list of device ids, each one describing an instance to set up.
    The function is also given a class.
    A new instance of the class is created for every device id, and the device id is given to the constructor of the class
    """
    if device_args is None:
        device_args = ()
    new_devices: list[MySensorsDevice] = []
    new_dev_ids: list[DevId] = discovery_info[ATTR_DEVICES]
    for dev_id in new_dev_ids:
        devices: dict[DevId, MySensorsDevice] = get_mysensors_devices(hass, domain)
        if dev_id in devices:
            _LOGGER.debug(
                "Skipping setup of %s for platform %s as it already exists",
                dev_id,
                domain,
            )
            continue
        gateway_id, node_id, child_id, value_type = dev_id
        gateway: BaseAsyncGateway | None = get_mysensors_gateway(hass, gateway_id)
        if not gateway:
            _LOGGER.warning("Skipping setup of %s, no gateway found", dev_id)
            continue
        device_class_copy = device_class
        if isinstance(device_class, dict):
            child = gateway.sensors[node_id].children[child_id]
            s_type = gateway.const.Presentation(child.type).name
            device_class_copy = device_class[s_type]

        args_copy = (*device_args, gateway_id, gateway, node_id, child_id, value_type)
        devices[dev_id] = device_class_copy(*args_copy)
        new_devices.append(devices[dev_id])
    if new_devices:
        _LOGGER.info("Adding new devices: %s", new_devices)
        if async_add_entities is not None:
            async_add_entities(new_devices, True)
    return new_devices
