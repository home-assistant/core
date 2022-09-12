"""Support for MQTT message handling."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any, cast

import jinja2
import voluptuous as vol

from homeassistant import config as conf_util, config_entries
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DISCOVERY,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_USERNAME,
    SERVICE_RELOAD,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    HassJob,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.exceptions import TemplateError, Unauthorized
from homeassistant.helpers import (
    config_validation as cv,
    discovery_flow,
    event,
    template,
)
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.reload import (
    async_integration_yaml_config,
    async_reload_integration_platforms,
)
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

# Loading the config flow file will register the flow
from . import debug_info, discovery
from .client import (  # noqa: F401
    MQTT,
    async_publish,
    async_subscribe,
    publish,
    subscribe,
)
from .config_integration import (
    CONFIG_SCHEMA_BASE,
    DEFAULT_VALUES,
    DEPRECATED_CONFIG_KEYS,
)
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
    DATA_MQTT,
    DATA_MQTT_CONFIG,
    DATA_MQTT_DISCOVERY_REGISTRY_HOOKS,
    DATA_MQTT_RELOAD_DISPATCHERS,
    DATA_MQTT_RELOAD_ENTRY,
    DATA_MQTT_RELOAD_NEEDED,
    DATA_MQTT_SUBSCRIPTIONS_TO_RESTORE,
    DATA_MQTT_UPDATED_CONFIG,
    DEFAULT_ENCODING,
    DEFAULT_QOS,
    DEFAULT_RETAIN,
    DOMAIN,
    MQTT_CONNECTED,
    MQTT_DISCONNECTED,
    PLATFORMS,
    RELOADABLE_PLATFORMS,
)
from .mixins import async_discover_yaml_entities
from .models import (  # noqa: F401
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)
from .util import (
    _VALID_QOS_SCHEMA,
    mqtt_config_entry_enabled,
    valid_publish_topic,
    valid_subscribe_topic,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_PUBLISH = "publish"
SERVICE_DUMP = "dump"

MANDATORY_DEFAULT_VALUES = (CONF_PORT,)

ATTR_TOPIC_TEMPLATE = "topic_template"
ATTR_PAYLOAD_TEMPLATE = "payload_template"

MAX_RECONNECT_WAIT = 300  # seconds

CONNECTION_SUCCESS = "connection_success"
CONNECTION_FAILED = "connection_failed"
CONNECTION_FAILED_RECOVERABLE = "connection_failed_recoverable"

CONFIG_ENTRY_CONFIG_KEYS = [
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_DISCOVERY,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_WILL_MESSAGE,
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_BIRTH_MESSAGE),  # Deprecated in HA Core 2022.3
            cv.deprecated(CONF_BROKER),  # Deprecated in HA Core 2022.3
            cv.deprecated(CONF_DISCOVERY),  # Deprecated in HA Core 2022.3
            cv.deprecated(CONF_PASSWORD),  # Deprecated in HA Core 2022.3
            cv.deprecated(CONF_PORT),  # Deprecated in HA Core 2022.3
            cv.deprecated(CONF_TLS_VERSION),  # Deprecated June 2020
            cv.deprecated(CONF_USERNAME),  # Deprecated in HA Core 2022.3
            cv.deprecated(CONF_WILL_MESSAGE),  # Deprecated in HA Core 2022.3
            CONFIG_SCHEMA_BASE,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


# Service call validation schema
MQTT_PUBLISH_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(ATTR_TOPIC, CONF_TOPIC): valid_publish_topic,
            vol.Exclusive(ATTR_TOPIC_TEMPLATE, CONF_TOPIC): cv.string,
            vol.Exclusive(ATTR_PAYLOAD, CONF_PAYLOAD): cv.string,
            vol.Exclusive(ATTR_PAYLOAD_TEMPLATE, CONF_PAYLOAD): cv.string,
            vol.Optional(ATTR_QOS, default=DEFAULT_QOS): _VALID_QOS_SCHEMA,
            vol.Optional(ATTR_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        },
        required=True,
    ),
    cv.has_at_least_one_key(ATTR_TOPIC, ATTR_TOPIC_TEMPLATE),
)


async def _async_setup_discovery(
    hass: HomeAssistant, conf: ConfigType, config_entry
) -> None:
    """Try to start the discovery of MQTT devices.

    This method is a coroutine.
    """
    await discovery.async_start(hass, conf[CONF_DISCOVERY_PREFIX], config_entry)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Start the MQTT protocol service."""
    conf: ConfigType | None = config.get(DOMAIN)

    websocket_api.async_register_command(hass, websocket_subscribe)
    websocket_api.async_register_command(hass, websocket_mqtt_info)
    debug_info.initialize(hass)

    if conf:
        conf = dict(conf)
        hass.data[DATA_MQTT_CONFIG] = conf

    if (mqtt_entry_status := mqtt_config_entry_enabled(hass)) is None:
        # Create an import flow if the user has yaml configured entities etc.
        # but no broker configuration. Note: The intention is not for this to
        # import broker configuration from YAML because that has been deprecated.
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={},
        )
        hass.data[DATA_MQTT_RELOAD_NEEDED] = True
    elif mqtt_entry_status is False:
        _LOGGER.info(
            "MQTT will be not available until the config entry is enabled",
        )
        hass.data[DATA_MQTT_RELOAD_NEEDED] = True

    return True


def _filter_entry_config(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove unknown keys from config entry data.

    Extra keys may have been added when importing MQTT yaml configuration.
    """
    filtered_data = {
        k: entry.data[k] for k in CONFIG_ENTRY_CONFIG_KEYS if k in entry.data
    }
    if entry.data.keys() != filtered_data.keys():
        _LOGGER.warning(
            "The following unsupported configuration options were removed from the "
            "MQTT config entry: %s. Add them to configuration.yaml if they are needed",
            entry.data.keys() - filtered_data.keys(),
        )
        hass.config_entries.async_update_entry(entry, data=filtered_data)


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


async def async_fetch_config(hass: HomeAssistant, entry: ConfigEntry) -> dict | None:
    """Fetch fresh MQTT yaml config from the hass config when (re)loading the entry."""
    if DATA_MQTT_RELOAD_ENTRY in hass.data:
        hass_config = await conf_util.async_hass_config_yaml(hass)
        mqtt_config = CONFIG_SCHEMA_BASE(hass_config.get(DOMAIN, {}))
        hass.data[DATA_MQTT_CONFIG] = mqtt_config

    # Remove unknown keys from config entry data
    _filter_entry_config(hass, entry)

    # Merge basic configuration, and add missing defaults for basic options
    _merge_basic_config(hass, entry, hass.data.get(DATA_MQTT_CONFIG, {}))
    # Bail out if broker setting is missing
    if CONF_BROKER not in entry.data:
        _LOGGER.error("MQTT broker is not configured, please configure it")
        return None

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
    return conf


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    # Merge basic configuration, and add missing defaults for basic options
    if (conf := await async_fetch_config(hass, entry)) is None:
        # Bail out
        return False

    hass.data[DATA_MQTT_DISCOVERY_REGISTRY_HOOKS] = {}
    hass.data[DATA_MQTT] = MQTT(hass, entry, conf)
    # Restore saved subscriptions
    if DATA_MQTT_SUBSCRIPTIONS_TO_RESTORE in hass.data:
        hass.data[DATA_MQTT].subscriptions = hass.data.pop(
            DATA_MQTT_SUBSCRIPTIONS_TO_RESTORE
        )
    entry.add_update_listener(_async_config_entry_updated)

    await hass.data[DATA_MQTT].async_connect()

    async def async_publish_service(call: ServiceCall) -> None:
        """Handle MQTT publish service calls."""
        msg_topic = call.data.get(ATTR_TOPIC)
        msg_topic_template = call.data.get(ATTR_TOPIC_TEMPLATE)
        payload = call.data.get(ATTR_PAYLOAD)
        payload_template = call.data.get(ATTR_PAYLOAD_TEMPLATE)
        qos: int = call.data[ATTR_QOS]
        retain: bool = call.data[ATTR_RETAIN]
        if msg_topic_template is not None:
            try:
                rendered_topic = template.Template(
                    msg_topic_template, hass
                ).async_render(parse_result=False)
                msg_topic = valid_publish_topic(rendered_topic)
            except (jinja2.TemplateError, TemplateError) as exc:
                _LOGGER.error(
                    "Unable to publish: rendering topic template of %s "
                    "failed because %s",
                    msg_topic_template,
                    exc,
                )
                return
            except vol.Invalid as err:
                _LOGGER.error(
                    "Unable to publish: topic template '%s' produced an "
                    "invalid topic '%s' after rendering (%s)",
                    msg_topic_template,
                    rendered_topic,
                    err,
                )
                return

        if payload_template is not None:
            try:
                payload = MqttCommandTemplate(
                    template.Template(payload_template), hass=hass
                ).async_render()
            except (jinja2.TemplateError, TemplateError) as exc:
                _LOGGER.error(
                    "Unable to publish to %s: rendering payload template of "
                    "%s failed because %s",
                    msg_topic,
                    payload_template,
                    exc,
                )
                return

        await hass.data[DATA_MQTT].async_publish(msg_topic, payload, qos, retain)

    hass.services.async_register(
        DOMAIN, SERVICE_PUBLISH, async_publish_service, schema=MQTT_PUBLISH_SCHEMA
    )

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
    hass.data[CONFIG_ENTRY_IS_SETUP] = set()

    async def async_setup_reload_service() -> None:
        """Create the reload service for the MQTT domain."""
        if hass.services.has_service(DOMAIN, SERVICE_RELOAD):
            return

        async def _reload_config(call: ServiceCall) -> None:
            """Reload the platforms."""
            # Reload the legacy yaml platform
            await async_reload_integration_platforms(hass, DOMAIN, RELOADABLE_PLATFORMS)

            # Reload the modern yaml platforms
            config_yaml = await async_integration_yaml_config(hass, DOMAIN) or {}
            hass.data[DATA_MQTT_UPDATED_CONFIG] = config_yaml.get(DOMAIN, {})
            await asyncio.gather(
                *(
                    [
                        async_discover_yaml_entities(hass, component)
                        for component in RELOADABLE_PLATFORMS
                    ]
                )
            )

            # Fire event
            hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

        async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)

    async def async_forward_entry_setup_and_setup_discovery(config_entry):
        """Forward the config entry setup to the platforms and set up discovery."""
        reload_manual_setup: bool = False
        # Local import to avoid circular dependencies
        # pylint: disable-next=import-outside-toplevel
        from . import device_automation, tag

        # Forward the entry setup to the MQTT platforms
        await asyncio.gather(
            *(
                [
                    device_automation.async_setup_entry(hass, config_entry),
                    tag.async_setup_entry(hass, config_entry),
                ]
                + [
                    hass.config_entries.async_forward_entry_setup(entry, component)
                    for component in PLATFORMS
                ]
            )
        )
        # Setup discovery
        if conf.get(CONF_DISCOVERY):
            await _async_setup_discovery(hass, conf, entry)
        # Setup reload service after all platforms have loaded
        await async_setup_reload_service()
        # When the entry is reloaded, also reload manual set up items to enable MQTT
        if DATA_MQTT_RELOAD_ENTRY in hass.data:
            hass.data.pop(DATA_MQTT_RELOAD_ENTRY)
            reload_manual_setup = True

        # When the entry was disabled before, reload manual set up items to enable MQTT again
        if DATA_MQTT_RELOAD_NEEDED in hass.data:
            hass.data.pop(DATA_MQTT_RELOAD_NEEDED)
            reload_manual_setup = True

        if reload_manual_setup:
            await async_reload_manual_mqtt_items(hass)

    await async_forward_entry_setup_and_setup_discovery(entry)

    return True


async def async_reload_manual_mqtt_items(hass: HomeAssistant) -> None:
    """Reload manual configured MQTT items."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RELOAD,
        {},
        blocking=True,
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "mqtt/device/debug_info", vol.Required("device_id"): str}
)
@callback
def websocket_mqtt_info(hass, connection, msg):
    """Get MQTT debug info for device."""
    device_id = msg["device_id"]
    mqtt_info = debug_info.info_for_device(hass, device_id)

    connection.send_result(msg["id"], mqtt_info)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "mqtt/subscribe",
        vol.Required("topic"): valid_subscribe_topic,
    }
)
@websocket_api.async_response
async def websocket_subscribe(hass, connection, msg):
    """Subscribe to a MQTT topic."""
    if not connection.user.is_admin:
        raise Unauthorized

    async def forward_messages(mqttmsg: ReceiveMessage):
        """Forward events to websocket."""
        try:
            payload = cast(bytes, mqttmsg.payload).decode(
                DEFAULT_ENCODING
            )  # not str because encoding is set to None
        except (AttributeError, UnicodeDecodeError):
            # Convert non UTF-8 payload to a string presentation
            payload = str(mqttmsg.payload)

        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "topic": mqttmsg.topic,
                    "payload": payload,
                    "qos": mqttmsg.qos,
                    "retain": mqttmsg.retain,
                },
            )
        )

    # Perform UTF-8 decoding directly in callback routine
    connection.subscriptions[msg["id"]] = await async_subscribe(
        hass, msg["topic"], forward_messages, encoding=None
    )

    connection.send_message(websocket_api.result_message(msg["id"]))


ConnectionStatusCallback = Callable[[bool], None]


@callback
def async_subscribe_connection_status(
    hass: HomeAssistant, connection_status_callback: ConnectionStatusCallback
) -> Callable[[], None]:
    """Subscribe to MQTT connection changes."""
    connection_status_callback_job = HassJob(connection_status_callback)

    async def connected():
        task = hass.async_run_hass_job(connection_status_callback_job, True)
        if task:
            await task

    async def disconnected():
        task = hass.async_run_hass_job(connection_status_callback_job, False)
        if task:
            await task

    subscriptions = {
        "connect": async_dispatcher_connect(hass, MQTT_CONNECTED, connected),
        "disconnect": async_dispatcher_connect(hass, MQTT_DISCONNECTED, disconnected),
    }

    @callback
    def unsubscribe():
        subscriptions["connect"]()
        subscriptions["disconnect"]()

    return unsubscribe


def is_connected(hass: HomeAssistant) -> bool:
    """Return if MQTT client is connected."""
    return hass.data[DATA_MQTT].connected


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove MQTT config entry from a device."""
    # pylint: disable-next=import-outside-toplevel
    from . import device_automation

    await device_automation.async_removed_from_device(hass, device_entry.id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload MQTT dump and publish service when the config entry is unloaded."""
    # Unload publish and dump services.
    hass.services.async_remove(
        DOMAIN,
        SERVICE_PUBLISH,
    )
    hass.services.async_remove(
        DOMAIN,
        SERVICE_DUMP,
    )

    # Stop the discovery
    await discovery.async_stop(hass)
    mqtt_client: MQTT = hass.data[DATA_MQTT]
    # Unload the platforms
    await asyncio.gather(
        *(
            hass.config_entries.async_forward_entry_unload(entry, component)
            for component in PLATFORMS
        )
    )
    await hass.async_block_till_done()
    # Unsubscribe reload dispatchers
    while reload_dispatchers := hass.data.setdefault(DATA_MQTT_RELOAD_DISPATCHERS, []):
        reload_dispatchers.pop()()
    hass.data[CONFIG_ENTRY_IS_SETUP] = set()
    # Cleanup listeners
    mqtt_client.cleanup()

    # Trigger reload manual MQTT items at entry setup
    if (mqtt_entry_status := mqtt_config_entry_enabled(hass)) is False:
        # The entry is disabled reload legacy manual items when the entry is enabled again
        hass.data[DATA_MQTT_RELOAD_NEEDED] = True
    elif mqtt_entry_status is True:
        # The entry is reloaded:
        # Trigger re-fetching the yaml config at entry setup
        hass.data[DATA_MQTT_RELOAD_ENTRY] = True
    # Reload the legacy yaml platform to make entities unavailable
    await async_reload_integration_platforms(hass, DOMAIN, RELOADABLE_PLATFORMS)
    # Cleanup entity registry hooks
    registry_hooks: dict[tuple, CALLBACK_TYPE] = hass.data[
        DATA_MQTT_DISCOVERY_REGISTRY_HOOKS
    ]
    while registry_hooks:
        registry_hooks.popitem()[1]()
    # Wait for all ACKs and stop the loop
    await mqtt_client.async_disconnect()
    # Store remaining subscriptions to be able to restore or reload them
    # when the entry is set up again
    if mqtt_client.subscriptions:
        hass.data[DATA_MQTT_SUBSCRIPTIONS_TO_RESTORE] = mqtt_client.subscriptions

    return True
