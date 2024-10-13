"""Support for MQTT message handling."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol

from homeassistant import config as conf_util
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DISCOVERY, CONF_PAYLOAD, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigValidationError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    event as ev,
    issue_registry as ir,
    template,
)
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration, async_get_loaded_integration
from homeassistant.setup import SetupPhases, async_pause_setup
from homeassistant.util.async_ import create_eager_task

# Loading the config flow file will register the flow
from . import debug_info, discovery
from .client import (  # noqa: F401
    MQTT,
    async_publish,
    async_subscribe,
    async_subscribe_internal,
    publish,
    subscribe,
)
from .config import MQTT_BASE_SCHEMA, MQTT_RO_SCHEMA, MQTT_RW_SCHEMA  # noqa: F401
from .config_integration import CONFIG_SCHEMA_BASE
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
    DEFAULT_DISCOVERY,
    DEFAULT_ENCODING,
    DEFAULT_PREFIX,
    DEFAULT_QOS,
    DEFAULT_RETAIN,
    DOMAIN,
    MQTT_CONNECTION_STATE,
    RELOADABLE_PLATFORMS,
    TEMPLATE_ERRORS,
)
from .models import (  # noqa: F401
    DATA_MQTT,
    DATA_MQTT_AVAILABLE,
    MqttCommandTemplate,
    MqttData,
    MqttValueTemplate,
    PayloadSentinel,
    PublishPayloadType,
    ReceiveMessage,
    convert_outgoing_mqtt_payload,
)
from .subscription import (  # noqa: F401
    EntitySubscription,
    async_prepare_subscribe_topics,
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from .util import (  # noqa: F401
    async_create_certificate_temp_files,
    async_forward_entry_setup_and_setup_discovery,
    async_wait_for_mqtt_client,
    mqtt_config_entry_enabled,
    platforms_from_config,
    valid_publish_topic,
    valid_qos_schema,
    valid_subscribe_topic,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_PUBLISH = "publish"
SERVICE_DUMP = "dump"

ATTR_TOPIC_TEMPLATE = "topic_template"
ATTR_PAYLOAD_TEMPLATE = "payload_template"
ATTR_EVALUATE_PAYLOAD = "evaluate_payload"

MAX_RECONNECT_WAIT = 300  # seconds

CONNECTION_SUCCESS = "connection_success"
CONNECTION_FAILED = "connection_failed"
CONNECTION_FAILED_RECOVERABLE = "connection_failed_recoverable"

# We accept 2 schemes for configuring manual MQTT items
#
# Preferred style:
#
# mqtt:
#   - {domain}:
#       name: ""
#       ...
#   - {domain}:
#       name: ""
#       ...
# ```
#
# Legacy supported style:
#
# mqtt:
#   {domain}:
#     - name: ""
#       ...
#     - name: ""
#       ...
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            cv.remove_falsy,
            [CONFIG_SCHEMA_BASE],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


# The use of a topic_template and payload_template in an mqtt publish action call
# have been deprecated with HA Core 2024.8.0 and will be removed with HA Core 2025.2.0

# Publish action call validation schema
MQTT_PUBLISH_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(ATTR_TOPIC, CONF_TOPIC): valid_publish_topic,
            vol.Exclusive(ATTR_TOPIC_TEMPLATE, CONF_TOPIC): cv.string,
            vol.Exclusive(ATTR_PAYLOAD, CONF_PAYLOAD): cv.string,
            vol.Exclusive(ATTR_PAYLOAD_TEMPLATE, CONF_PAYLOAD): cv.string,
            vol.Optional(ATTR_EVALUATE_PAYLOAD): cv.boolean,
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


@callback
def _async_remove_mqtt_issues(hass: HomeAssistant, mqtt_data: MqttData) -> None:
    """Unregister open config issues."""
    issue_registry = ir.async_get(hass)
    open_issues = [
        issue_id
        for (domain, issue_id), issue_entry in issue_registry.issues.items()
        if domain == DOMAIN and issue_entry.translation_key == "invalid_platform_config"
    ]
    for issue in open_issues:
        ir.async_delete_issue(hass, DOMAIN, issue)


async def async_check_config_schema(
    hass: HomeAssistant, config_yaml: ConfigType
) -> None:
    """Validate manually configured MQTT items."""
    mqtt_data = hass.data[DATA_MQTT]
    mqtt_config: list[dict[str, list[ConfigType]]] = config_yaml.get(DOMAIN, {})
    for mqtt_config_item in mqtt_config:
        for domain, config_items in mqtt_config_item.items():
            schema = mqtt_data.reload_schema[domain]
            for config in config_items:
                try:
                    schema(config)
                except vol.Invalid as exc:
                    integration = await async_get_integration(hass, DOMAIN)
                    message = conf_util.format_schema_error(
                        hass, exc, domain, config, integration.documentation
                    )
                    raise ServiceValidationError(
                        message,
                        translation_domain=DOMAIN,
                        translation_key="invalid_platform_config",
                        translation_placeholders={
                            "domain": domain,
                        },
                    ) from exc


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    conf: dict[str, Any]
    mqtt_data: MqttData

    async def _setup_client(
        client_available: asyncio.Future[bool],
    ) -> tuple[MqttData, dict[str, Any]]:
        """Set up the MQTT client."""
        # Fetch configuration
        conf = dict(entry.data)
        hass_config = await conf_util.async_hass_config_yaml(hass)
        mqtt_yaml = CONFIG_SCHEMA(hass_config).get(DOMAIN, [])
        await async_create_certificate_temp_files(hass, conf)
        client = MQTT(hass, entry, conf)
        if DOMAIN in hass.data:
            mqtt_data = hass.data[DATA_MQTT]
            mqtt_data.config = mqtt_yaml
            mqtt_data.client = client
        else:
            # Initial setup
            websocket_api.async_register_command(hass, websocket_subscribe)
            websocket_api.async_register_command(hass, websocket_mqtt_info)
            hass.data[DATA_MQTT] = mqtt_data = MqttData(config=mqtt_yaml, client=client)
        await client.async_start(mqtt_data)

        # Restore saved subscriptions
        if mqtt_data.subscriptions_to_restore:
            mqtt_data.client.async_restore_tracked_subscriptions(
                mqtt_data.subscriptions_to_restore
            )
            mqtt_data.subscriptions_to_restore = set()
        mqtt_data.reload_dispatchers.append(
            entry.add_update_listener(_async_config_entry_updated)
        )

        return (mqtt_data, conf)

    client_available: asyncio.Future[bool]
    if DATA_MQTT_AVAILABLE not in hass.data:
        client_available = hass.data[DATA_MQTT_AVAILABLE] = hass.loop.create_future()
    else:
        client_available = hass.data[DATA_MQTT_AVAILABLE]

    mqtt_data, conf = await _setup_client(client_available)
    platforms_used = platforms_from_config(mqtt_data.config)
    platforms_used.update(
        entry.domain
        for entry in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    )
    integration = async_get_loaded_integration(hass, DOMAIN)
    # Preload platforms we know we are going to use so
    # discovery can setup each platform synchronously
    # and avoid creating a flood of tasks at startup
    # while waiting for the the imports to complete
    if not integration.platforms_are_loaded(platforms_used):
        with async_pause_setup(hass, SetupPhases.WAIT_IMPORT_PLATFORMS):
            await integration.async_get_platforms(platforms_used)

    # Wait to connect until the platforms are loaded so
    # we can be sure discovery does not have to wait for
    # each platform to load when we get the flood of retained
    # messages on connect
    await mqtt_data.client.async_connect(client_available)

    async def async_publish_service(call: ServiceCall) -> None:
        """Handle MQTT publish service calls."""
        msg_topic: str | None = call.data.get(ATTR_TOPIC)
        msg_topic_template: str | None = call.data.get(ATTR_TOPIC_TEMPLATE)
        payload: PublishPayloadType = call.data.get(ATTR_PAYLOAD)
        evaluate_payload: bool = call.data.get(ATTR_EVALUATE_PAYLOAD, False)
        payload_template: str | None = call.data.get(ATTR_PAYLOAD_TEMPLATE)
        qos: int = call.data[ATTR_QOS]
        retain: bool = call.data[ATTR_RETAIN]
        if msg_topic_template is not None:
            # The use of a topic_template in an mqtt publish action call
            # has been deprecated with HA Core 2024.8.0
            # and will be removed with HA Core 2025.2.0
            rendered_topic: Any = MqttCommandTemplate(
                template.Template(msg_topic_template, hass),
            ).async_render()
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"topic_template_deprecation_{rendered_topic}",
                breaks_in_ha_version="2025.2.0",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="topic_template_deprecation",
                translation_placeholders={
                    "topic_template": msg_topic_template,
                    "topic": rendered_topic,
                },
            )
            try:
                msg_topic = valid_publish_topic(rendered_topic)
            except vol.Invalid as err:
                err_str = str(err)
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_publish_topic",
                    translation_placeholders={
                        "error": err_str,
                        "topic": str(rendered_topic),
                        "topic_template": str(msg_topic_template),
                    },
                ) from err

        if payload_template is not None:
            # The use of a payload_template in an mqtt publish action call
            # has been deprecated with HA Core 2024.8.0
            # and will be removed with HA Core 2025.2.0
            if TYPE_CHECKING:
                assert msg_topic is not None
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"payload_template_deprecation_{msg_topic}",
                breaks_in_ha_version="2025.2.0",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="payload_template_deprecation",
                translation_placeholders={
                    "topic": msg_topic,
                    "payload_template": payload_template,
                },
            )
            payload = MqttCommandTemplate(
                template.Template(payload_template, hass)
            ).async_render()
        elif evaluate_payload:
            # Convert quoted binary literal to raw data
            payload = convert_outgoing_mqtt_payload(payload)

        if TYPE_CHECKING:
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

        unsub = async_subscribe_internal(hass, call.data["topic"], collect_msg)

        def write_dump() -> None:
            with open(hass.config.path("mqtt_dump.txt"), "w", encoding="utf8") as fp:
                for msg in messages:
                    fp.write(",".join(msg) + "\n")

        async def finish_dump(_: datetime) -> None:
            """Write dump to file."""
            unsub()
            await hass.async_add_executor_job(write_dump)

        ev.async_call_later(hass, call.data["duration"], finish_dump)

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
    async def _reload_config(call: ServiceCall) -> None:
        """Reload the platforms."""
        # Fetch updated manually configured items and validate
        try:
            config_yaml = await async_integration_yaml_config(
                hass, DOMAIN, raise_on_failure=True
            )
        except ConfigValidationError as ex:
            raise ServiceValidationError(
                translation_domain=ex.translation_domain,
                translation_key=ex.translation_key,
                translation_placeholders=ex.translation_placeholders,
            ) from ex

        new_config: list[ConfigType] = config_yaml.get(DOMAIN, [])
        platforms_used = platforms_from_config(new_config)
        new_platforms = platforms_used - mqtt_data.platforms_loaded
        await async_forward_entry_setup_and_setup_discovery(hass, entry, new_platforms)
        # Check the schema before continuing reload
        await async_check_config_schema(hass, config_yaml)

        # Remove repair issues
        _async_remove_mqtt_issues(hass, mqtt_data)

        mqtt_data.config = new_config

        # Reload the modern yaml platforms
        mqtt_platforms = async_get_platforms(hass, DOMAIN)
        tasks = [
            create_eager_task(entity.async_remove())
            for mqtt_platform in mqtt_platforms
            for entity in list(mqtt_platform.entities.values())
            if getattr(entity, "_discovery_data", None) is None
            and mqtt_platform.config_entry
            and mqtt_platform.domain in RELOADABLE_PLATFORMS
        ]
        await asyncio.gather(*tasks)

        for component in mqtt_data.reload_handlers.values():
            component()

        # Fire event
        hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

    await async_forward_entry_setup_and_setup_discovery(hass, entry, platforms_used)
    # Setup reload service after all platforms have loaded
    if not hass.services.has_service(DOMAIN, SERVICE_RELOAD):
        async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)
    # Setup discovery
    if conf.get(CONF_DISCOVERY, DEFAULT_DISCOVERY):
        await discovery.async_start(
            hass, conf.get(CONF_DISCOVERY_PREFIX, DEFAULT_PREFIX), entry
        )

    return True


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
    qos: int = msg.get("qos", DEFAULT_QOS)
    connection.subscriptions[msg["id"]] = async_subscribe_internal(
        hass, msg["topic"], forward_messages, encoding=None, qos=qos
    )

    connection.send_message(websocket_api.result_message(msg["id"]))


type ConnectionStatusCallback = Callable[[bool], None]


@callback
def async_subscribe_connection_status(
    hass: HomeAssistant, connection_status_callback: ConnectionStatusCallback
) -> Callable[[], None]:
    """Subscribe to MQTT connection changes."""
    return async_dispatcher_connect(
        hass, MQTT_CONNECTION_STATE, connection_status_callback
    )


def is_connected(hass: HomeAssistant) -> bool:
    """Return if MQTT client is connected."""
    mqtt_data = hass.data[DATA_MQTT]
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
    mqtt_data = hass.data[DATA_MQTT]
    mqtt_client = mqtt_data.client

    # Unload publish and dump services.
    hass.services.async_remove(DOMAIN, SERVICE_PUBLISH)
    hass.services.async_remove(DOMAIN, SERVICE_DUMP)

    # Stop the discovery
    await discovery.async_stop(hass)
    # Unload the platforms
    await hass.config_entries.async_unload_platforms(entry, mqtt_data.platforms_loaded)
    mqtt_data.platforms_loaded = set()
    await asyncio.sleep(0)
    # Unsubscribe reload dispatchers
    while reload_dispatchers := mqtt_data.reload_dispatchers:
        reload_dispatchers.pop()()
    # Cleanup listeners
    mqtt_client.cleanup()

    # Cleanup entity registry hooks
    registry_hooks = mqtt_data.discovery_registry_hooks
    while registry_hooks:
        registry_hooks.popitem()[1]()
    # Wait for all ACKs, stop the loop and disconnect the client
    await mqtt_client.async_disconnect(disconnect_paho_client=True)

    # Cleanup MQTT client availability
    hass.data.pop(DATA_MQTT_AVAILABLE, None)
    # Store remaining subscriptions to be able to restore or reload them
    # when the entry is set up again
    if subscriptions := mqtt_client.subscriptions:
        mqtt_data.subscriptions_to_restore = subscriptions

    # Remove repair issues
    _async_remove_mqtt_issues(hass, mqtt_data)

    return True
