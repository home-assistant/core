"""Support for MQTT message handling."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any, cast

import jinja2
import voluptuous as vol

from homeassistant import config as conf_util
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_DISCOVERY,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    SERVICE_RELOAD,
)
from homeassistant.core import HassJob, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import TemplateError, Unauthorized
from homeassistant.helpers import config_validation as cv, event, template
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import async_get_platforms
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
from .config_integration import PLATFORM_CONFIG_SCHEMA_BASE
from .const import (  # noqa: F401
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_CERTIFICATE,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_COMMAND_TOPIC,
    CONF_DISCOVERY_PREFIX,
    CONF_KEEPALIVE,
    CONF_QOS,
    CONF_STATE_TOPIC,
    CONF_TLS_INSECURE,
    CONF_TOPIC,
    CONF_TRANSPORT,
    CONF_WILL_MESSAGE,
    CONF_WS_HEADERS,
    CONF_WS_PATH,
    DATA_MQTT,
    DATA_MQTT_AVAILABLE,
    DEFAULT_DISCOVERY,
    DEFAULT_ENCODING,
    DEFAULT_PREFIX,
    DEFAULT_QOS,
    DEFAULT_RETAIN,
    DOMAIN,
    MQTT_CONNECTED,
    MQTT_DISCONNECTED,
    PLATFORMS,
    RELOADABLE_PLATFORMS,
)
from .models import (  # noqa: F401
    MqttCommandTemplate,
    MqttData,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)
from .util import (  # noqa: F401
    async_create_certificate_temp_files,
    async_wait_for_mqtt_client,
    get_mqtt_data,
    mqtt_config_entry_enabled,
    valid_publish_topic,
    valid_qos_schema,
    valid_subscribe_topic,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_PUBLISH = "publish"
SERVICE_DUMP = "dump"

ATTR_TOPIC_TEMPLATE = "topic_template"
ATTR_PAYLOAD_TEMPLATE = "payload_template"

MAX_RECONNECT_WAIT = 300  # seconds

CONNECTION_SUCCESS = "connection_success"
CONNECTION_FAILED = "connection_failed"
CONNECTION_FAILED_RECOVERABLE = "connection_failed_recoverable"

CONFIG_ENTRY_CONFIG_KEYS = [
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_CERTIFICATE,
    CONF_CLIENT_ID,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_DISCOVERY,
    CONF_DISCOVERY_PREFIX,
    CONF_KEEPALIVE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TLS_INSECURE,
    CONF_TRANSPORT,
    CONF_WS_PATH,
    CONF_WS_HEADERS,
    CONF_USERNAME,
    CONF_WILL_MESSAGE,
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.removed(CONF_BIRTH_MESSAGE),  # Removed in HA Core 2023.4
            cv.removed(CONF_BROKER),  # Removed in HA Core 2023.4
            cv.removed(CONF_CERTIFICATE),  # Removed in HA Core 2023.4
            cv.removed(CONF_CLIENT_ID),  # Removed in HA Core 2023.4
            cv.removed(CONF_CLIENT_CERT),  # Removed in HA Core 2023.4
            cv.removed(CONF_CLIENT_KEY),  # Removed in HA Core 2023.4
            cv.removed(CONF_DISCOVERY),  # Removed in HA Core 2022.3
            cv.removed(CONF_DISCOVERY_PREFIX),  # Removed in HA Core 2023.4
            cv.removed(CONF_KEEPALIVE),  # Removed in HA Core 2023.4
            cv.removed(CONF_PASSWORD),  # Removed in HA Core 2023.4
            cv.removed(CONF_PORT),  # Removed in HA Core 2023.4
            cv.removed(CONF_PROTOCOL),  # Removed in HA Core 2023.4
            cv.removed(CONF_TLS_INSECURE),  # Removed in HA Core 2023.4
            cv.removed(CONF_USERNAME),  # Removed in HA Core 2023.4
            cv.removed(CONF_WILL_MESSAGE),  # Removed in HA Core 2023.4
            PLATFORM_CONFIG_SCHEMA_BASE,
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
            vol.Optional(ATTR_QOS, default=DEFAULT_QOS): valid_qos_schema,
            vol.Optional(ATTR_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        },
        required=True,
    ),
    cv.has_at_least_one_key(ATTR_TOPIC, ATTR_TOPIC_TEMPLATE),
)


async def _async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle signals of config entry being updated.

    Causes for this is config entry options changing.
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    conf: dict[str, Any]
    mqtt_data: MqttData

    async def _setup_client() -> tuple[MqttData, dict[str, Any]]:
        """Set up the MQTT client."""
        # Fetch configuration
        conf = dict(entry.data)
        hass_config = await conf_util.async_hass_config_yaml(hass)
        mqtt_yaml = PLATFORM_CONFIG_SCHEMA_BASE(hass_config.get(DOMAIN, {}))
        client = MQTT(hass, entry, conf)
        if DOMAIN in hass.data:
            mqtt_data = get_mqtt_data(hass)
            mqtt_data.config = mqtt_yaml
            mqtt_data.client = client
        else:
            # Initial setup
            websocket_api.async_register_command(hass, websocket_subscribe)
            websocket_api.async_register_command(hass, websocket_mqtt_info)
            hass.data[DATA_MQTT] = mqtt_data = MqttData(config=mqtt_yaml, client=client)
        client.start(mqtt_data)

        await async_create_certificate_temp_files(hass, dict(entry.data))
        # Restore saved subscriptions
        if mqtt_data.subscriptions_to_restore:
            mqtt_data.client.async_restore_tracked_subscriptions(
                mqtt_data.subscriptions_to_restore
            )
            mqtt_data.subscriptions_to_restore = []
        mqtt_data.reload_dispatchers.append(
            entry.add_update_listener(_async_config_entry_updated)
        )

        await mqtt_data.client.async_connect()
        return (mqtt_data, conf)

    client_available: asyncio.Future[bool]
    if DATA_MQTT_AVAILABLE not in hass.data:
        client_available = hass.data[DATA_MQTT_AVAILABLE] = asyncio.Future()
    else:
        client_available = hass.data[DATA_MQTT_AVAILABLE]

    setup_ok: bool = False
    try:
        mqtt_data, conf = await _setup_client()
        setup_ok = True
    finally:
        if not client_available.done():
            client_available.set_result(setup_ok)

    async def async_publish_service(call: ServiceCall) -> None:
        """Handle MQTT publish service calls."""
        msg_topic: str | None = call.data.get(ATTR_TOPIC)
        msg_topic_template: str | None = call.data.get(ATTR_TOPIC_TEMPLATE)
        payload: PublishPayloadType = call.data.get(ATTR_PAYLOAD)
        payload_template: str | None = call.data.get(ATTR_PAYLOAD_TEMPLATE)
        qos: int = call.data[ATTR_QOS]
        retain: bool = call.data[ATTR_RETAIN]
        if msg_topic_template is not None:
            try:
                rendered_topic: Any = template.Template(
                    msg_topic_template, hass
                ).async_render(parse_result=False)
                msg_topic = valid_publish_topic(rendered_topic)
            except (jinja2.TemplateError, TemplateError) as exc:
                _LOGGER.error(
                    (
                        "Unable to publish: rendering topic template of %s "
                        "failed because %s"
                    ),
                    msg_topic_template,
                    exc,
                )
                return
            except vol.Invalid as err:
                _LOGGER.error(
                    (
                        "Unable to publish: topic template '%s' produced an "
                        "invalid topic '%s' after rendering (%s)"
                    ),
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
                    (
                        "Unable to publish to %s: rendering payload template of "
                        "%s failed because %s"
                    ),
                    msg_topic,
                    payload_template,
                    exc,
                )
                return

        assert msg_topic is not None
        await mqtt_data.client.async_publish(msg_topic, payload, qos, retain)

    hass.services.async_register(
        DOMAIN, SERVICE_PUBLISH, async_publish_service, schema=MQTT_PUBLISH_SCHEMA
    )

    async def async_dump_service(call: ServiceCall) -> None:
        """Handle MQTT dump service calls."""
        messages: list[tuple[str, str]] = []

        @callback
        def collect_msg(msg: ReceiveMessage) -> None:
            messages.append((msg.topic, str(msg.payload).replace("\n", "")))

        unsub = await async_subscribe(hass, call.data["topic"], collect_msg)

        def write_dump() -> None:
            with open(hass.config.path("mqtt_dump.txt"), "w", encoding="utf8") as fp:
                for msg in messages:
                    fp.write(",".join(msg) + "\n")

        async def finish_dump(_: datetime) -> None:
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

    async def async_setup_reload_service() -> None:
        """Create the reload service for the MQTT domain."""
        if hass.services.has_service(DOMAIN, SERVICE_RELOAD):
            return

        async def _reload_config(call: ServiceCall) -> None:
            """Reload the platforms."""
            # Fetch updated manual configured items and validate
            config_yaml = await async_integration_yaml_config(hass, DOMAIN) or {}
            mqtt_data.updated_config = config_yaml.get(DOMAIN, {})

            # Reload the modern yaml platforms
            mqtt_platforms = async_get_platforms(hass, DOMAIN)
            tasks = [
                entity.async_remove()
                for mqtt_platform in mqtt_platforms
                for entity in mqtt_platform.entities.values()
                # pylint: disable-next=protected-access
                if not entity._discovery_data  # type: ignore[attr-defined]
                if mqtt_platform.config_entry
                and mqtt_platform.domain in RELOADABLE_PLATFORMS
            ]
            await asyncio.gather(*tasks)

            await asyncio.gather(
                *(
                    [
                        mqtt_data.reload_handlers[component]()
                        for component in RELOADABLE_PLATFORMS
                        if component in mqtt_data.reload_handlers
                    ]
                )
            )

            # Fire event
            hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

        async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)

    async def async_forward_entry_setup_and_setup_discovery(
        config_entry: ConfigEntry,
        conf: ConfigType,
    ) -> None:
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
        if conf.get(CONF_DISCOVERY, DEFAULT_DISCOVERY):
            await discovery.async_start(
                hass, conf.get(CONF_DISCOVERY_PREFIX, DEFAULT_PREFIX), entry
            )
        # Setup reload service after all platforms have loaded
        await async_setup_reload_service()
        # When the entry is reloaded, also reload manual set up items to enable MQTT
        if mqtt_data.reload_entry:
            mqtt_data.reload_entry = False
            reload_manual_setup = True

        # When the entry was disabled before, reload manual set up items to enable
        # MQTT again
        if mqtt_data.reload_needed:
            mqtt_data.reload_needed = False
            reload_manual_setup = True

        if reload_manual_setup:
            await async_reload_manual_mqtt_items(hass)

    await async_forward_entry_setup_and_setup_discovery(entry, conf)

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
def websocket_mqtt_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get MQTT debug info for device."""
    device_id = msg["device_id"]
    mqtt_info = debug_info.info_for_device(hass, device_id)

    connection.send_result(msg["id"], mqtt_info)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "mqtt/subscribe",
        vol.Required("topic"): valid_subscribe_topic,
        vol.Optional("qos"): valid_qos_schema,
    }
)
@websocket_api.async_response
async def websocket_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe to a MQTT topic."""
    if not connection.user.is_admin:
        raise Unauthorized

    @callback
    def forward_messages(mqttmsg: ReceiveMessage) -> None:
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
    qos: int = msg["qos"] if "qos" in msg else DEFAULT_QOS
    connection.subscriptions[msg["id"]] = await async_subscribe(
        hass, msg["topic"], forward_messages, encoding=None, qos=qos
    )

    connection.send_message(websocket_api.result_message(msg["id"]))


ConnectionStatusCallback = Callable[[bool], None]


@callback
def async_subscribe_connection_status(
    hass: HomeAssistant, connection_status_callback: ConnectionStatusCallback
) -> Callable[[], None]:
    """Subscribe to MQTT connection changes."""
    connection_status_callback_job = HassJob(connection_status_callback)

    async def connected() -> None:
        task = hass.async_run_hass_job(connection_status_callback_job, True)
        if task:
            await task

    async def disconnected() -> None:
        task = hass.async_run_hass_job(connection_status_callback_job, False)
        if task:
            await task

    subscriptions = {
        "connect": async_dispatcher_connect(hass, MQTT_CONNECTED, connected),
        "disconnect": async_dispatcher_connect(hass, MQTT_DISCONNECTED, disconnected),
    }

    @callback
    def unsubscribe() -> None:
        subscriptions["connect"]()
        subscriptions["disconnect"]()

    return unsubscribe


def is_connected(hass: HomeAssistant) -> bool:
    """Return if MQTT client is connected."""
    mqtt_data = get_mqtt_data(hass)
    return mqtt_data.client.connected


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
    mqtt_data = get_mqtt_data(hass)
    mqtt_client = mqtt_data.client

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
    # Unload the platforms
    await asyncio.gather(
        *(
            hass.config_entries.async_forward_entry_unload(entry, component)
            for component in PLATFORMS
        )
    )
    await asyncio.sleep(0)
    # Unsubscribe reload dispatchers
    while reload_dispatchers := mqtt_data.reload_dispatchers:
        reload_dispatchers.pop()()
    # Cleanup listeners
    mqtt_client.cleanup()

    # Trigger reload manual MQTT items at entry setup
    if (mqtt_entry_status := mqtt_config_entry_enabled(hass)) is False:
        # The entry is disabled reload legacy manual items when
        # the entry is enabled again
        mqtt_data.reload_needed = True
    elif mqtt_entry_status is True:
        # The entry is reloaded:
        # Trigger re-fetching the yaml config at entry setup
        mqtt_data.reload_entry = True
    # Reload the legacy yaml platform to make entities unavailable
    await async_reload_integration_platforms(hass, DOMAIN, RELOADABLE_PLATFORMS)
    # Cleanup entity registry hooks
    registry_hooks = mqtt_data.discovery_registry_hooks
    while registry_hooks:
        registry_hooks.popitem()[1]()
    # Wait for all ACKs and stop the loop
    await mqtt_client.async_disconnect()

    # Cleanup MQTT client availability
    hass.data.pop(DATA_MQTT_AVAILABLE, None)
    # Store remaining subscriptions to be able to restore or reload them
    # when the entry is set up again
    if subscriptions := mqtt_client.subscriptions:
        mqtt_data.subscriptions_to_restore = subscriptions

    return True
