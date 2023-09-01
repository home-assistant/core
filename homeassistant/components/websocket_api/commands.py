"""Commands part of Websocket API."""
from __future__ import annotations

from collections.abc import Callable
import datetime as dt
from functools import lru_cache, partial
import json
from typing import Any, cast

import voluptuous as vol

from homeassistant.auth.models import User
from homeassistant.auth.permissions.const import CAT_ENTITIES, POLICY_READ
from homeassistant.const import (
    EVENT_STATE_CHANGED,
    MATCH_ALL,
    SIGNAL_BOOTSTRAP_INTEGRATIONS,
)
from homeassistant.core import Context, Event, HomeAssistant, State, callback
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotFound,
    TemplateError,
    Unauthorized,
)
from homeassistant.helpers import config_validation as cv, entity, template
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (
    EventStateChangedData,
    TrackTemplate,
    TrackTemplateResult,
    async_track_template_result,
)
from homeassistant.helpers.json import (
    JSON_DUMP,
    ExtendedJSONEncoder,
    find_paths_unserializable_data,
    json_dumps,
)
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.helpers.typing import EventType
from homeassistant.loader import (
    Integration,
    IntegrationNotFound,
    async_get_integration,
    async_get_integration_descriptions,
    async_get_integrations,
)
from homeassistant.setup import DATA_SETUP_TIME, async_get_loaded_integrations
from homeassistant.util.json import format_unserializable_data

from . import const, decorators, messages
from .connection import ActiveConnection
from .const import ERR_NOT_FOUND
from .messages import construct_event_message, construct_result_message

ALL_SERVICE_DESCRIPTIONS_JSON_CACHE = "websocket_api_all_service_descriptions_json"


@callback
def async_register_commands(
    hass: HomeAssistant,
    async_reg: Callable[[HomeAssistant, const.WebSocketCommandHandler], None],
) -> None:
    """Register commands."""
    async_reg(hass, handle_call_service)
    async_reg(hass, handle_entity_source)
    async_reg(hass, handle_execute_script)
    async_reg(hass, handle_fire_event)
    async_reg(hass, handle_get_config)
    async_reg(hass, handle_get_services)
    async_reg(hass, handle_get_states)
    async_reg(hass, handle_manifest_get)
    async_reg(hass, handle_integration_setup_info)
    async_reg(hass, handle_manifest_list)
    async_reg(hass, handle_ping)
    async_reg(hass, handle_render_template)
    async_reg(hass, handle_subscribe_bootstrap_integrations)
    async_reg(hass, handle_subscribe_events)
    async_reg(hass, handle_subscribe_trigger)
    async_reg(hass, handle_test_condition)
    async_reg(hass, handle_unsubscribe_events)
    async_reg(hass, handle_validate_config)
    async_reg(hass, handle_subscribe_entities)
    async_reg(hass, handle_supported_features)
    async_reg(hass, handle_integration_descriptions)


def pong_message(iden: int) -> dict[str, Any]:
    """Return a pong message."""
    return {"id": iden, "type": "pong"}


def _forward_events_check_permissions(
    send_message: Callable[[str | dict[str, Any] | Callable[[], str]], None],
    user: User,
    msg_id: int,
    event: Event,
) -> None:
    """Forward state changed events to websocket."""
    # We have to lookup the permissions again because the user might have
    # changed since the subscription was created.
    permissions = user.permissions
    if not permissions.access_all_entities(
        POLICY_READ
    ) and not permissions.check_entity(event.data["entity_id"], POLICY_READ):
        return
    send_message(messages.cached_event_message(msg_id, event))


def _forward_events_unconditional(
    send_message: Callable[[str | dict[str, Any] | Callable[[], str]], None],
    msg_id: int,
    event: Event,
) -> None:
    """Forward events to websocket."""
    send_message(messages.cached_event_message(msg_id, event))


@callback
@decorators.websocket_command(
    {
        vol.Required("type"): "subscribe_events",
        vol.Optional("event_type", default=MATCH_ALL): str,
    }
)
def handle_subscribe_events(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe events command."""
    # Circular dep
    # pylint: disable-next=import-outside-toplevel
    from .permissions import SUBSCRIBE_ALLOWLIST

    event_type = msg["event_type"]

    if event_type not in SUBSCRIBE_ALLOWLIST and not connection.user.is_admin:
        raise Unauthorized

    if event_type == EVENT_STATE_CHANGED:
        forward_events = callback(
            partial(
                _forward_events_check_permissions,
                connection.send_message,
                connection.user,
                msg["id"],
            )
        )
    else:
        forward_events = callback(
            partial(_forward_events_unconditional, connection.send_message, msg["id"])
        )

    connection.subscriptions[msg["id"]] = hass.bus.async_listen(
        event_type, forward_events, run_immediately=True
    )

    connection.send_result(msg["id"])


@callback
@decorators.websocket_command(
    {
        vol.Required("type"): "subscribe_bootstrap_integrations",
    }
)
def handle_subscribe_bootstrap_integrations(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe bootstrap integrations command."""

    @callback
    def forward_bootstrap_integrations(message: dict[str, Any]) -> None:
        """Forward bootstrap integrations to websocket."""
        connection.send_message(messages.event_message(msg["id"], message))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, SIGNAL_BOOTSTRAP_INTEGRATIONS, forward_bootstrap_integrations
    )

    connection.send_result(msg["id"])


@callback
@decorators.websocket_command(
    {
        vol.Required("type"): "unsubscribe_events",
        vol.Required("subscription"): cv.positive_int,
    }
)
def handle_unsubscribe_events(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle unsubscribe events command."""
    subscription = msg["subscription"]

    if subscription in connection.subscriptions:
        connection.subscriptions.pop(subscription)()
        connection.send_result(msg["id"])
    else:
        connection.send_error(msg["id"], const.ERR_NOT_FOUND, "Subscription not found.")


@decorators.websocket_command(
    {
        vol.Required("type"): "call_service",
        vol.Required("domain"): str,
        vol.Required("service"): str,
        vol.Optional("target"): cv.ENTITY_SERVICE_FIELDS,
        vol.Optional("service_data"): dict,
    }
)
@decorators.async_response
async def handle_call_service(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle call service command."""
    blocking = True
    # We do not support templates.
    target = msg.get("target")
    if template.is_complex(target):
        raise vol.Invalid("Templates are not supported here")

    try:
        context = connection.context(msg)
        await hass.services.async_call(
            msg["domain"],
            msg["service"],
            msg.get("service_data"),
            blocking,
            context,
            target=target,
        )
        connection.send_result(msg["id"], {"context": context})
    except ServiceNotFound as err:
        if err.domain == msg["domain"] and err.service == msg["service"]:
            connection.send_error(msg["id"], const.ERR_NOT_FOUND, "Service not found.")
        else:
            connection.send_error(msg["id"], const.ERR_HOME_ASSISTANT_ERROR, str(err))
    except vol.Invalid as err:
        connection.send_error(msg["id"], const.ERR_INVALID_FORMAT, str(err))
    except HomeAssistantError as err:
        connection.logger.exception(err)
        connection.send_error(msg["id"], const.ERR_HOME_ASSISTANT_ERROR, str(err))
    except Exception as err:  # pylint: disable=broad-except
        connection.logger.exception(err)
        connection.send_error(msg["id"], const.ERR_UNKNOWN_ERROR, str(err))


@callback
def _async_get_allowed_states(
    hass: HomeAssistant, connection: ActiveConnection
) -> list[State]:
    if connection.user.permissions.access_all_entities(POLICY_READ):
        return hass.states.async_all()
    entity_perm = connection.user.permissions.check_entity
    return [
        state
        for state in hass.states.async_all()
        if entity_perm(state.entity_id, POLICY_READ)
    ]


@callback
@decorators.websocket_command({vol.Required("type"): "get_states"})
def handle_get_states(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle get states command."""
    states = _async_get_allowed_states(hass, connection)

    try:
        serialized_states = [state.as_dict_json() for state in states]
    except (ValueError, TypeError):
        pass
    else:
        _send_handle_get_states_response(connection, msg["id"], serialized_states)
        return

    # If we can't serialize, we'll filter out unserializable states
    serialized_states = []
    for state in states:
        try:
            serialized_states.append(state.as_dict_json())
        except (ValueError, TypeError):
            connection.logger.error(
                "Unable to serialize to JSON. Bad data found at %s",
                format_unserializable_data(
                    find_paths_unserializable_data(state, dump=JSON_DUMP)
                ),
            )

    _send_handle_get_states_response(connection, msg["id"], serialized_states)


def _send_handle_get_states_response(
    connection: ActiveConnection, msg_id: int, serialized_states: list[str]
) -> None:
    """Send handle get states response."""
    joined_states = ",".join(serialized_states)
    connection.send_message(construct_result_message(msg_id, f"[{joined_states}]"))


def _forward_entity_changes(
    send_message: Callable[[str | dict[str, Any] | Callable[[], str]], None],
    entity_ids: set[str],
    user: User,
    msg_id: int,
    event: Event,
) -> None:
    """Forward entity state changed events to websocket."""
    entity_id = event.data["entity_id"]
    if entity_ids and entity_id not in entity_ids:
        return
    # We have to lookup the permissions again because the user might have
    # changed since the subscription was created.
    permissions = user.permissions
    if not permissions.access_all_entities(
        POLICY_READ
    ) and not permissions.check_entity(event.data["entity_id"], POLICY_READ):
        return
    send_message(messages.cached_state_diff_message(msg_id, event))


@callback
@decorators.websocket_command(
    {
        vol.Required("type"): "subscribe_entities",
        vol.Optional("entity_ids"): cv.entity_ids,
    }
)
def handle_subscribe_entities(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe entities command."""
    entity_ids = set(msg.get("entity_ids", []))
    # We must never await between sending the states and listening for
    # state changed events or we will introduce a race condition
    # where some states are missed
    states = _async_get_allowed_states(hass, connection)
    connection.subscriptions[msg["id"]] = hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        callback(
            partial(
                _forward_entity_changes,
                connection.send_message,
                entity_ids,
                connection.user,
                msg["id"],
            )
        ),
        run_immediately=True,
    )
    connection.send_result(msg["id"])

    # JSON serialize here so we can recover if it blows up due to the
    # state machine containing unserializable data. This command is required
    # to succeed for the UI to show.
    try:
        serialized_states = [
            state.as_compressed_state_json()
            for state in states
            if not entity_ids or state.entity_id in entity_ids
        ]
    except (ValueError, TypeError):
        pass
    else:
        _send_handle_entities_init_response(connection, msg["id"], serialized_states)
        return

    serialized_states = []
    for state in states:
        try:
            serialized_states.append(state.as_compressed_state_json())
        except (ValueError, TypeError):
            connection.logger.error(
                "Unable to serialize to JSON. Bad data found at %s",
                format_unserializable_data(
                    find_paths_unserializable_data(state, dump=JSON_DUMP)
                ),
            )

    _send_handle_entities_init_response(connection, msg["id"], serialized_states)


def _send_handle_entities_init_response(
    connection: ActiveConnection, msg_id: int, serialized_states: list[str]
) -> None:
    """Send handle entities init response."""
    joined_states = ",".join(serialized_states)
    connection.send_message(
        construct_event_message(msg_id, f'{{"a":{{{joined_states}}}}}')
    )


async def _async_get_all_descriptions_json(hass: HomeAssistant) -> str:
    """Return JSON of descriptions (i.e. user documentation) for all service calls."""
    descriptions = await async_get_all_descriptions(hass)
    if ALL_SERVICE_DESCRIPTIONS_JSON_CACHE in hass.data:
        cached_descriptions, cached_json_payload = hass.data[
            ALL_SERVICE_DESCRIPTIONS_JSON_CACHE
        ]
        # If the descriptions are the same, return the cached JSON payload
        if cached_descriptions is descriptions:
            return cast(str, cached_json_payload)
    json_payload = json_dumps(descriptions)
    hass.data[ALL_SERVICE_DESCRIPTIONS_JSON_CACHE] = (descriptions, json_payload)
    return json_payload


@decorators.websocket_command({vol.Required("type"): "get_services"})
@decorators.async_response
async def handle_get_services(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle get services command."""
    payload = await _async_get_all_descriptions_json(hass)
    connection.send_message(construct_result_message(msg["id"], payload))


@callback
@decorators.websocket_command({vol.Required("type"): "get_config"})
def handle_get_config(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle get config command."""
    connection.send_result(msg["id"], hass.config.as_dict())


@decorators.websocket_command(
    {vol.Required("type"): "manifest/list", vol.Optional("integrations"): [str]}
)
@decorators.async_response
async def handle_manifest_list(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle integrations command."""
    wanted_integrations = msg.get("integrations")
    if wanted_integrations is None:
        wanted_integrations = async_get_loaded_integrations(hass)

    ints_or_excs = await async_get_integrations(hass, wanted_integrations)
    integrations: list[Integration] = []
    for int_or_exc in ints_or_excs.values():
        if isinstance(int_or_exc, Exception):
            raise int_or_exc
        integrations.append(int_or_exc)
    connection.send_result(
        msg["id"], [integration.manifest for integration in integrations]
    )


@decorators.websocket_command(
    {vol.Required("type"): "manifest/get", vol.Required("integration"): str}
)
@decorators.async_response
async def handle_manifest_get(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle integrations command."""
    try:
        integration = await async_get_integration(hass, msg["integration"])
        connection.send_result(msg["id"], integration.manifest)
    except IntegrationNotFound:
        connection.send_error(msg["id"], const.ERR_NOT_FOUND, "Integration not found")


@callback
@decorators.websocket_command({vol.Required("type"): "integration/setup_info"})
def handle_integration_setup_info(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle integrations command."""
    connection.send_result(
        msg["id"],
        [
            {"domain": integration, "seconds": timedelta.total_seconds()}
            for integration, timedelta in cast(
                dict[str, dt.timedelta], hass.data[DATA_SETUP_TIME]
            ).items()
        ],
    )


@callback
@decorators.websocket_command({vol.Required("type"): "ping"})
def handle_ping(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle ping command."""
    connection.send_message(pong_message(msg["id"]))


@lru_cache
def _cached_template(template_str: str, hass: HomeAssistant) -> template.Template:
    """Return a cached template."""
    return template.Template(template_str, hass)


@decorators.websocket_command(
    {
        vol.Required("type"): "render_template",
        vol.Required("template"): str,
        vol.Optional("entity_ids"): cv.entity_ids,
        vol.Optional("variables"): dict,
        vol.Optional("timeout"): vol.Coerce(float),
        vol.Optional("strict", default=False): bool,
    }
)
@decorators.async_response
async def handle_render_template(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle render_template command."""
    template_str = msg["template"]
    template_obj = _cached_template(template_str, hass)
    variables = msg.get("variables")
    timeout = msg.get("timeout")
    info = None

    if timeout:
        try:
            timed_out = await template_obj.async_render_will_timeout(
                timeout, variables, strict=msg["strict"]
            )
        except TemplateError as ex:
            connection.send_error(msg["id"], const.ERR_TEMPLATE_ERROR, str(ex))
            return

        if timed_out:
            connection.send_error(
                msg["id"],
                const.ERR_TEMPLATE_ERROR,
                f"Exceeded maximum execution time of {timeout}s",
            )
            return

    @callback
    def _template_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        nonlocal info
        track_template_result = updates.pop()
        result = track_template_result.result
        if isinstance(result, TemplateError):
            connection.send_error(msg["id"], const.ERR_TEMPLATE_ERROR, str(result))
            return

        connection.send_message(
            messages.event_message(
                msg["id"], {"result": result, "listeners": info.listeners}  # type: ignore[attr-defined]
            )
        )

    try:
        info = async_track_template_result(
            hass,
            [TrackTemplate(template_obj, variables)],
            _template_listener,
            raise_on_template_error=True,
            strict=msg["strict"],
        )
    except TemplateError as ex:
        connection.send_error(msg["id"], const.ERR_TEMPLATE_ERROR, str(ex))
        return

    connection.subscriptions[msg["id"]] = info.async_remove

    connection.send_result(msg["id"])

    hass.loop.call_soon_threadsafe(info.async_refresh)


@callback
@decorators.websocket_command(
    {vol.Required("type"): "entity/source", vol.Optional("entity_id"): [cv.entity_id]}
)
def handle_entity_source(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle entity source command."""
    raw_sources = entity.entity_sources(hass)
    entity_perm = connection.user.permissions.check_entity

    if "entity_id" not in msg:
        if connection.user.permissions.access_all_entities(POLICY_READ):
            sources = raw_sources
        else:
            sources = {
                entity_id: source
                for entity_id, source in raw_sources.items()
                if entity_perm(entity_id, POLICY_READ)
            }

        connection.send_result(msg["id"], sources)
        return

    sources = {}

    for entity_id in msg["entity_id"]:
        if not entity_perm(entity_id, POLICY_READ):
            raise Unauthorized(
                context=connection.context(msg),
                permission=POLICY_READ,
                perm_category=CAT_ENTITIES,
            )

        if (source := raw_sources.get(entity_id)) is None:
            connection.send_error(msg["id"], ERR_NOT_FOUND, "Entity not found")
            return

        sources[entity_id] = source

    connection.send_result(msg["id"], sources)


@decorators.websocket_command(
    {
        vol.Required("type"): "subscribe_trigger",
        vol.Required("trigger"): cv.TRIGGER_SCHEMA,
        vol.Optional("variables"): dict,
    }
)
@decorators.require_admin
@decorators.async_response
async def handle_subscribe_trigger(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe trigger command."""
    # Circular dep
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.helpers import trigger

    trigger_config = await trigger.async_validate_trigger_config(hass, msg["trigger"])

    @callback
    def forward_triggers(
        variables: dict[str, Any], context: Context | None = None
    ) -> None:
        """Forward events to websocket."""
        message = messages.event_message(
            msg["id"], {"variables": variables, "context": context}
        )
        connection.send_message(
            json.dumps(
                message, cls=ExtendedJSONEncoder, allow_nan=False, separators=(",", ":")
            )
        )

    connection.subscriptions[msg["id"]] = (
        await trigger.async_initialize_triggers(
            hass,
            trigger_config,
            forward_triggers,
            const.DOMAIN,
            const.DOMAIN,
            connection.logger.log,
            variables=msg.get("variables"),
        )
    ) or (
        # Some triggers won't return an unsub function. Since the caller expects
        # a subscription, we're going to fake one.
        lambda: None
    )
    connection.send_result(msg["id"])


@decorators.websocket_command(
    {
        vol.Required("type"): "test_condition",
        vol.Required("condition"): cv.CONDITION_SCHEMA,
        vol.Optional("variables"): dict,
    }
)
@decorators.require_admin
@decorators.async_response
async def handle_test_condition(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle test condition command."""
    # Circular dep
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.helpers import condition

    # Do static + dynamic validation of the condition
    config = await condition.async_validate_condition_config(hass, msg["condition"])
    # Test the condition
    check_condition = await condition.async_from_config(hass, config)
    connection.send_result(
        msg["id"], {"result": check_condition(hass, msg.get("variables"))}
    )


@decorators.websocket_command(
    {
        vol.Required("type"): "execute_script",
        vol.Required("sequence"): cv.SCRIPT_SCHEMA,
        vol.Optional("variables"): dict,
    }
)
@decorators.require_admin
@decorators.async_response
async def handle_execute_script(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle execute script command."""
    # Circular dep
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.helpers.script import Script, async_validate_actions_config

    script_config = await async_validate_actions_config(hass, msg["sequence"])

    context = connection.context(msg)
    script_obj = Script(hass, script_config, f"{const.DOMAIN} script", const.DOMAIN)
    script_result = await script_obj.async_run(msg.get("variables"), context=context)
    connection.send_result(
        msg["id"],
        {
            "context": context,
            "response": script_result.service_response if script_result else None,
        },
    )


@callback
@decorators.websocket_command(
    {
        vol.Required("type"): "fire_event",
        vol.Required("event_type"): str,
        vol.Optional("event_data"): dict,
    }
)
@decorators.require_admin
def handle_fire_event(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle fire event command."""
    context = connection.context(msg)

    hass.bus.async_fire(msg["event_type"], msg.get("event_data"), context=context)
    connection.send_result(msg["id"], {"context": context})


@decorators.websocket_command(
    {
        vol.Required("type"): "validate_config",
        vol.Optional("trigger"): cv.match_all,
        vol.Optional("condition"): cv.match_all,
        vol.Optional("action"): cv.match_all,
    }
)
@decorators.async_response
async def handle_validate_config(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle validate config command."""
    # Circular dep
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.helpers import condition, script, trigger

    result = {}

    for key, schema, validator in (
        ("trigger", cv.TRIGGER_SCHEMA, trigger.async_validate_trigger_config),
        ("condition", cv.CONDITIONS_SCHEMA, condition.async_validate_conditions_config),
        ("action", cv.SCRIPT_SCHEMA, script.async_validate_actions_config),
    ):
        if key not in msg:
            continue

        try:
            await validator(hass, schema(msg[key]))
        except vol.Invalid as err:
            result[key] = {"valid": False, "error": str(err)}
        else:
            result[key] = {"valid": True, "error": None}

    connection.send_result(msg["id"], result)


@callback
@decorators.websocket_command(
    {
        vol.Required("type"): "supported_features",
        vol.Required("features"): {str: int},
    }
)
def handle_supported_features(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle setting supported features."""
    connection.set_supported_features(msg["features"])
    connection.send_result(msg["id"])


@decorators.require_admin
@decorators.websocket_command({"type": "integration/descriptions"})
@decorators.async_response
async def handle_integration_descriptions(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get metadata for all brands and integrations."""
    connection.send_result(msg["id"], await async_get_integration_descriptions(hass))
