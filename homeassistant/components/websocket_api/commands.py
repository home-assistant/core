"""Commands part of Websocket API."""
from __future__ import annotations

from collections.abc import Callable
import datetime as dt
import json
from typing import Any, cast

import voluptuous as vol

from homeassistant.auth.permissions.const import CAT_ENTITIES, POLICY_READ
from homeassistant.const import (
    EVENT_STATE_CHANGED,
    MATCH_ALL,
    SIGNAL_BOOTSTRAP_INTEGRATONS,
)
from homeassistant.core import Context, Event, HomeAssistant, State, callback
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotFound,
    TemplateError,
    Unauthorized,
)
from homeassistant.generated import supported_brands
from homeassistant.helpers import config_validation as cv, entity, template
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    async_track_template_result,
)
from homeassistant.helpers.json import JSON_DUMP, ExtendedJSONEncoder
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.loader import (
    Integration,
    IntegrationNotFound,
    async_get_integration,
    async_get_integration_descriptions,
    async_get_integrations,
)
from homeassistant.setup import DATA_SETUP_TIME, async_get_loaded_integrations
from homeassistant.util.json import (
    find_paths_unserializable_data,
    format_unserializable_data,
)

from . import const, decorators, messages
from .connection import ActiveConnection
from .const import ERR_NOT_FOUND


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
    async_reg(hass, handle_supported_brands)
    async_reg(hass, handle_supported_features)
    async_reg(hass, handle_integration_descriptions)


def pong_message(iden: int) -> dict[str, Any]:
    """Return a pong message."""
    return {"id": iden, "type": "pong"}


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
    # pylint: disable=import-outside-toplevel
    from .permissions import SUBSCRIBE_ALLOWLIST

    event_type = msg["event_type"]

    if event_type not in SUBSCRIBE_ALLOWLIST and not connection.user.is_admin:
        raise Unauthorized

    if event_type == EVENT_STATE_CHANGED:

        @callback
        def forward_events(event: Event) -> None:
            """Forward state changed events to websocket."""
            if not connection.user.permissions.check_entity(
                event.data["entity_id"], POLICY_READ
            ):
                return

            connection.send_message(
                lambda: messages.cached_event_message(msg["id"], event)
            )

    else:

        @callback
        def forward_events(event: Event) -> None:
            """Forward events to websocket."""
            connection.send_message(
                lambda: messages.cached_event_message(msg["id"], event)
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
        hass, SIGNAL_BOOTSTRAP_INTEGRATONS, forward_bootstrap_integrations
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
    if connection.user.permissions.access_all_entities("read"):
        return hass.states.async_all()
    entity_perm = connection.user.permissions.check_entity
    return [
        state
        for state in hass.states.async_all()
        if entity_perm(state.entity_id, "read")
    ]


@callback
@decorators.websocket_command({vol.Required("type"): "get_states"})
def handle_get_states(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle get states command."""
    states = _async_get_allowed_states(hass, connection)

    # JSON serialize here so we can recover if it blows up due to the
    # state machine containing unserializable data. This command is required
    # to succeed for the UI to show.
    response = messages.result_message(msg["id"], states)
    try:
        connection.send_message(JSON_DUMP(response))
        return
    except (ValueError, TypeError):
        connection.logger.error(
            "Unable to serialize to JSON. Bad data found at %s",
            format_unserializable_data(
                find_paths_unserializable_data(response, dump=JSON_DUMP)
            ),
        )
    del response

    # If we can't serialize, we'll filter out unserializable states
    serialized = []
    for state in states:
        try:
            serialized.append(JSON_DUMP(state))
        except (ValueError, TypeError):
            # Error is already logged above
            pass

    # We now have partially serialized states. Craft some JSON.
    response2 = JSON_DUMP(messages.result_message(msg["id"], ["TO_REPLACE"]))
    response2 = response2.replace('"TO_REPLACE"', ", ".join(serialized))
    connection.send_message(response2)


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

    @callback
    def forward_entity_changes(event: Event) -> None:
        """Forward entity state changed events to websocket."""
        if not connection.user.permissions.check_entity(
            event.data["entity_id"], POLICY_READ
        ):
            return
        if entity_ids and event.data["entity_id"] not in entity_ids:
            return

        connection.send_message(
            lambda: messages.cached_state_diff_message(msg["id"], event)
        )

    # We must never await between sending the states and listening for
    # state changed events or we will introduce a race condition
    # where some states are missed
    states = _async_get_allowed_states(hass, connection)
    connection.subscriptions[msg["id"]] = hass.bus.async_listen(
        EVENT_STATE_CHANGED, forward_entity_changes, run_immediately=True
    )
    connection.send_result(msg["id"])
    data: dict[str, dict[str, dict]] = {
        messages.ENTITY_EVENT_ADD: {
            state.entity_id: messages.compressed_state_dict_add(state)
            for state in states
            if not entity_ids or state.entity_id in entity_ids
        }
    }

    # JSON serialize here so we can recover if it blows up due to the
    # state machine containing unserializable data. This command is required
    # to succeed for the UI to show.
    response = messages.event_message(msg["id"], data)
    try:
        connection.send_message(JSON_DUMP(response))
        return
    except (ValueError, TypeError):
        connection.logger.error(
            "Unable to serialize to JSON. Bad data found at %s",
            format_unserializable_data(
                find_paths_unserializable_data(response, dump=JSON_DUMP)
            ),
        )
    del response

    add_entities = data[messages.ENTITY_EVENT_ADD]
    cannot_serialize: list[str] = []
    for entity_id, state_dict in add_entities.items():
        try:
            JSON_DUMP(state_dict)
        except (ValueError, TypeError):
            cannot_serialize.append(entity_id)

    for entity_id in cannot_serialize:
        del add_entities[entity_id]

    connection.send_message(JSON_DUMP(messages.event_message(msg["id"], data)))


@decorators.websocket_command({vol.Required("type"): "get_services"})
@decorators.async_response
async def handle_get_services(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle get services command."""
    descriptions = await async_get_all_descriptions(hass)
    connection.send_result(msg["id"], descriptions)


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


@decorators.websocket_command({vol.Required("type"): "integration/setup_info"})
@decorators.async_response
async def handle_integration_setup_info(
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
    template_obj = template.Template(template_str, hass)  # type: ignore[no-untyped-call]
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
        event: Event | None, updates: list[TrackTemplateResult]
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
        if connection.user.permissions.access_all_entities("read"):
            sources = raw_sources
        else:
            sources = {
                entity_id: source
                for entity_id, source in raw_sources.items()
                if entity_perm(entity_id, "read")
            }

        connection.send_result(msg["id"], sources)
        return

    sources = {}

    for entity_id in msg["entity_id"]:
        if not entity_perm(entity_id, "read"):
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
    # pylint: disable=import-outside-toplevel
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
    # pylint: disable=import-outside-toplevel
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
    # pylint: disable=import-outside-toplevel
    from homeassistant.helpers.script import Script

    context = connection.context(msg)
    script_obj = Script(hass, msg["sequence"], f"{const.DOMAIN} script", const.DOMAIN)
    await script_obj.async_run(msg.get("variables"), context=context)
    connection.send_result(msg["id"], {"context": context})


@decorators.websocket_command(
    {
        vol.Required("type"): "fire_event",
        vol.Required("event_type"): str,
        vol.Optional("event_data"): dict,
    }
)
@decorators.require_admin
@decorators.async_response
async def handle_fire_event(
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
    # pylint: disable=import-outside-toplevel
    from homeassistant.helpers import condition, script, trigger

    result = {}

    for key, schema, validator in (
        ("trigger", cv.TRIGGER_SCHEMA, trigger.async_validate_trigger_config),
        ("condition", cv.CONDITION_SCHEMA, condition.async_validate_condition_config),
        ("action", cv.SCRIPT_SCHEMA, script.async_validate_actions_config),
    ):
        if key not in msg:
            continue

        try:
            await validator(hass, schema(msg[key]))  # type: ignore[operator]
        except vol.Invalid as err:
            result[key] = {"valid": False, "error": str(err)}
        else:
            result[key] = {"valid": True, "error": None}

    connection.send_result(msg["id"], result)


@decorators.websocket_command(
    {
        vol.Required("type"): "supported_brands",
    }
)
@decorators.async_response
async def handle_supported_brands(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle supported brands command."""
    data = {}

    ints_or_excs = await async_get_integrations(
        hass, supported_brands.HAS_SUPPORTED_BRANDS
    )
    for int_or_exc in ints_or_excs.values():
        if isinstance(int_or_exc, Exception):
            raise int_or_exc
        # Happens if a custom component without supported brands overrides a built-in one with supported brands
        if "supported_brands" not in int_or_exc.manifest:
            continue
        data[int_or_exc.domain] = int_or_exc.manifest["supported_brands"]
    connection.send_result(msg["id"], data)


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
    connection.supported_features = msg["features"]
    connection.send_result(msg["id"])


@decorators.require_admin
@decorators.websocket_command({"type": "integration/descriptions"})
@decorators.async_response
async def handle_integration_descriptions(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get metadata for all brands and integrations."""
    connection.send_result(msg["id"], await async_get_integration_descriptions(hass))
