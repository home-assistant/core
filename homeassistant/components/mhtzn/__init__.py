"""The Detailed Hello World Push integration."""
from __future__ import annotations

import logging
import asyncio
import voluptuous as vol

import datetime as dt
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HassJob, HomeAssistant, ServiceCall, callback
from homeassistant.data_entry_flow import BaseServiceInfo
from homeassistant.helpers import config_validation as cv, event, template
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType
from . import discovery
from .util import _VALID_QOS_SCHEMA, valid_publish_topic, valid_subscribe_topic

from .config import CONFIG_SCHEMA_BASE, DEFAULT_VALUES, DEPRECATED_CONFIG_KEYS, SCHEMA_BASE
from homeassistant.const import (
    CONF_NAME,
    CONF_DISCOVERY,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_RELOAD, CONF_VALUE_TEMPLATE,
)
from .client import (  # noqa: F401
    MQTT,
    async_publish,
    async_subscribe,
    publish,
    subscribe,
)
from . import hub
from .const import (  # noqa: F401
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_COMMAND_TOPIC,
    CONF_DISCOVERY_PREFIX,
    CONF_QOS,
    CONF_STATE_TOPIC,
    CONF_TLS_VERSION,
    CONF_TOPIC,
    CONF_WILL_MESSAGE,
    CONFIG_ENTRY_IS_SETUP,
    DATA_CONFIG_ENTRY_LOCK,
    DATA_MQTT,
    DATA_MQTT_CONFIG,
    DATA_MQTT_RELOAD_NEEDED,
    DEFAULT_ENCODING,
    DEFAULT_QOS,
    DEFAULT_RETAIN,
    DOMAIN,
    MQTT_CONNECTED,
    MQTT_DISCONNECTED,
    PLATFORMS, CONF_ENV_ID, CONF_RETAIN,
)

from .models import (  # noqa: F401
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)

_LOGGER = logging.getLogger(__name__)

# List of platforms to support. There should be a matching .py file for each,
# eg <cover.py> and <sensor.py>
PLATFORMS: list[str] = ["switch"]

MANDATORY_DEFAULT_VALUES = (CONF_PORT,)

SERVICE_PUBLISH = "publish"
SERVICE_DUMP = "dump"

MQTT_BASE_PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(SCHEMA_BASE)

# Switch type platforms publish to MQTT and may subscribe
MQTT_RW_PLATFORM_SCHEMA = MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
    }
)


@dataclass
class MqttServiceInfo(BaseServiceInfo):
    """Prepared info from mqtt entries."""

    topic: str
    payload: ReceivePayloadType
    qos: int
    retain: bool
    subscribed_topic: str
    timestamp: dt.datetime


def _merge_basic_config(
        hass: HomeAssistant, entry: ConfigEntry, yaml_config: dict[str, Any]
) -> None:
    """Merge basic options in configuration.yaml config with config entry.

    This mends incomplete migration from old version of HA Core.
    """

    entry_updated = False
    entry_config = {**entry.data}
    for key in DEPRECATED_CONFIG_KEYS:
        if key in yaml_config and key not in entry_config:
            entry_config[key] = yaml_config[key]
            entry_updated = True

    for key in MANDATORY_DEFAULT_VALUES:
        if key not in entry_config:
            entry_config[key] = DEFAULT_VALUES[key]
            entry_updated = True

    if entry_updated:
        hass.config_entries.async_update_entry(entry, data=entry_config)


def _merge_extended_config(entry, conf):
    """Merge advanced options in configuration.yaml config with config entry."""
    # Add default values
    conf = {**DEFAULT_VALUES, **conf}
    return {**conf, **entry.data}

async def async_remove_config_entry_device(
        hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True

async def _async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle signals of config entry being updated.

    Causes for this is config entry options changing.
    """
    mqtt_client = hass.data[DATA_MQTT]

    if (conf := hass.data.get(DATA_MQTT_CONFIG)) is None:
        conf = CONFIG_SCHEMA_BASE(dict(entry.data))

    mqtt_client.conf = _merge_extended_config(entry, conf)
    await mqtt_client.async_disconnect()
    mqtt_client.init_client()
    await mqtt_client.async_connect()

    await discovery.async_stop(hass)
    if mqtt_client.conf.get(CONF_DISCOVERY):
        await _async_setup_discovery(hass, mqtt_client.conf, entry)


async def _async_setup_discovery(
        hass: HomeAssistant, conf: ConfigType, config_entry
) -> None:
    """Try to start the discovery of MQTT devices.

    This method is a coroutine.
    """
    await discovery.async_start(hass, conf[CONF_DISCOVERY_PREFIX], conf[CONF_ENV_ID], config_entry)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello World from a config entry."""

    _merge_basic_config(hass, entry, hass.data.get(DATA_MQTT_CONFIG, {}))

    # Bail out if broker setting is missing
    if CONF_BROKER not in entry.data:
        _LOGGER.error("MQTT broker is not configured, please configure it")
        return False

    # If user doesn't have configuration.yaml config, generate default values
    # for options not in config entry data
    if (conf := hass.data.get(DATA_MQTT_CONFIG)) is None:
        conf = CONFIG_SCHEMA_BASE(dict(entry.data))

    # User has configuration.yaml config, warn about config entry overrides
    elif any(key in conf for key in entry.data):
        shared_keys = conf.keys() & entry.data.keys()
        override = {k: entry.data[k] for k in shared_keys if conf[k] != entry.data[k]}
        if CONF_PASSWORD in override:
            override[CONF_PASSWORD] = "********"
        if override:
            _LOGGER.warning(
                "Deprecated configuration settings found in configuration.yaml. "
                "These settings from your configuration entry will override: %s",
                override,
            )

    # Merge advanced configuration values from configuration.yaml
    conf = _merge_extended_config(entry, conf)

    hass.data[DATA_MQTT] = MQTT(
        hass,
        entry,
        conf,
    )
    entry.add_update_listener(_async_config_entry_updated)

    await hass.data[DATA_MQTT].async_connect()

    async def async_stop_mqtt(_event: Event):
        """Stop MQTT component."""
        await hass.data[DATA_MQTT].async_disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_mqtt)

    async def async_dump_service(call: ServiceCall) -> None:
        """Handle MQTT dump service calls."""
        messages = []

        @callback
        def collect_msg(msg):
            messages.append((msg.topic, msg.payload.replace("\n", "")))

        unsub = await async_subscribe(hass, call.data["topic"], collect_msg)

        def write_dump():
            with open(hass.config.path("mqtt_dump.txt"), "wt", encoding="utf8") as fp:
                for msg in messages:
                    fp.write(",".join(msg) + "\n")

        async def finish_dump(_):
            """Write dump to file."""
            unsub()
            await hass.async_add_executor_job(write_dump)

        event.async_call_later(hass, call.data["duration"], finish_dump)

    hass.services.async_register(
        DOMAIN,
        SERVICE_DUMP,
        async_dump_service,
        schema=vol.Schema(
            {
                vol.Required("topic"): valid_subscribe_topic,
                vol.Optional("duration", default=5): int,
            }
        ),
    )

    # setup platforms and discovery
    hass.data[DATA_CONFIG_ENTRY_LOCK] = asyncio.Lock()
    hass.data[CONFIG_ENTRY_IS_SETUP] = set()

    async def async_forward_entry_setup():
        """Forward the config entry setup to the platforms."""
        async with hass.data[DATA_CONFIG_ENTRY_LOCK]:
            for component in PLATFORMS:
                config_entries_key = f"{component}.mqtt"
                if config_entries_key not in hass.data[CONFIG_ENTRY_IS_SETUP]:
                    hass.data[CONFIG_ENTRY_IS_SETUP].add(config_entries_key)
                    await hass.config_entries.async_forward_entry_setup(
                        entry, component
                    )

    hass.async_create_task(async_forward_entry_setup())

    if conf.get(CONF_DISCOVERY):
        await _async_setup_discovery(hass, conf, entry)

    if DATA_MQTT_RELOAD_NEEDED in hass.data:
        hass.data.pop(DATA_MQTT_RELOAD_NEEDED)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=False,
        )

    return True

