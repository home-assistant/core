"""Commands part of Websocket API."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.auth.permissions.const import CAT_ENTITIES, POLICY_READ
from homeassistant.components.websocket_api.const import ERR_NOT_FOUND
from homeassistant.const import EVENT_STATE_CHANGED, EVENT_TIME_CHANGED, MATCH_ALL
from homeassistant.core import DOMAIN as HASS_DOMAIN, callback
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotFound,
    TemplateError,
    Unauthorized,
)
from homeassistant.helpers import config_validation as cv, entity
from homeassistant.helpers.event import async_track_template_result
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.loader import IntegrationNotFound, async_get_integration

from . import const, decorators, messages

_LOGGER = logging.getLogger(__name__)

# mypy: allow-untyped-calls, allow-untyped-defs


@callback
def async_register_commands(hass, async_reg):
    """Register commands."""
    async_reg(hass, handle_subscribe_events)
    async_reg(hass, handle_unsubscribe_events)
    async_reg(hass, handle_call_service)
    async_reg(hass, handle_get_states)
    async_reg(hass, handle_get_services)
    async_reg(hass, handle_get_config)
    async_reg(hass, handle_ping)
    async_reg(hass, handle_render_template)
    async_reg(hass, handle_manifest_list)
    async_reg(hass, handle_manifest_get)
    async_reg(hass, handle_entity_source)
    async_reg(hass, handle_subscribe_trigger)
    async_reg(hass, handle_test_condition)


def pong_message(iden):
    """Return a pong message."""
    return {"id": iden, "type": "pong"}


@callback
@decorators.websocket_command(
    {
        vol.Required("type"): "subscribe_events",
        vol.Optional("event_type", default=MATCH_ALL): str,
    }
)
def handle_subscribe_events(hass, connection, msg):
    """Handle subscribe events command."""
    # Circular dep
    # pylint: disable=import-outside-toplevel
    from .permissions import SUBSCRIBE_WHITELIST

    event_type = msg["event_type"]

    if event_type not in SUBSCRIBE_WHITELIST and not connection.user.is_admin:
        raise Unauthorized

    if event_type == EVENT_STATE_CHANGED:

        @callback
        def forward_events(event):
            """Forward state changed events to websocket."""
            if not connection.user.permissions.check_entity(
                event.data["entity_id"], POLICY_READ
            ):
                return

            connection.send_message(messages.event_message(msg["id"], event))

    else:

        @callback
        def forward_events(event):
            """Forward events to websocket."""
            if event.event_type == EVENT_TIME_CHANGED:
                return

            connection.send_message(messages.event_message(msg["id"], event.as_dict()))

    connection.subscriptions[msg["id"]] = hass.bus.async_listen(
        event_type, forward_events
    )

    connection.send_message(messages.result_message(msg["id"]))


@callback
@decorators.websocket_command(
    {
        vol.Required("type"): "unsubscribe_events",
        vol.Required("subscription"): cv.positive_int,
    }
)
def handle_unsubscribe_events(hass, connection, msg):
    """Handle unsubscribe events command."""
    subscription = msg["subscription"]

    if subscription in connection.subscriptions:
        connection.subscriptions.pop(subscription)()
        connection.send_message(messages.result_message(msg["id"]))
    else:
        connection.send_message(
            messages.error_message(
                msg["id"], const.ERR_NOT_FOUND, "Subscription not found."
            )
        )


@decorators.websocket_command(
    {
        vol.Required("type"): "call_service",
        vol.Required("domain"): str,
        vol.Required("service"): str,
        vol.Optional("service_data"): dict,
    }
)
@decorators.async_response
async def handle_call_service(hass, connection, msg):
    """Handle call service command."""
    blocking = True
    if msg["domain"] == HASS_DOMAIN and msg["service"] in ["restart", "stop"]:
        blocking = False

    try:
        await hass.services.async_call(
            msg["domain"],
            msg["service"],
            msg.get("service_data"),
            blocking,
            connection.context(msg),
        )
        connection.send_message(
            messages.result_message(msg["id"], {"context": connection.context(msg)})
        )
    except ServiceNotFound as err:
        if err.domain == msg["domain"] and err.service == msg["service"]:
            connection.send_message(
                messages.error_message(
                    msg["id"], const.ERR_NOT_FOUND, "Service not found."
                )
            )
        else:
            connection.send_message(
                messages.error_message(
                    msg["id"], const.ERR_HOME_ASSISTANT_ERROR, str(err)
                )
            )
    except HomeAssistantError as err:
        connection.logger.exception(err)
        connection.send_message(
            messages.error_message(msg["id"], const.ERR_HOME_ASSISTANT_ERROR, str(err))
        )
    except Exception as err:  # pylint: disable=broad-except
        connection.logger.exception(err)
        connection.send_message(
            messages.error_message(msg["id"], const.ERR_UNKNOWN_ERROR, str(err))
        )


@callback
@decorators.websocket_command({vol.Required("type"): "get_states"})
def handle_get_states(hass, connection, msg):
    """Handle get states command."""
    if connection.user.permissions.access_all_entities("read"):
        states = hass.states.async_all()
    else:
        entity_perm = connection.user.permissions.check_entity
        states = [
            state
            for state in hass.states.async_all()
            if entity_perm(state.entity_id, "read")
        ]

    connection.send_message(messages.result_message(msg["id"], states))


@decorators.websocket_command({vol.Required("type"): "get_services"})
@decorators.async_response
async def handle_get_services(hass, connection, msg):
    """Handle get services command."""
    descriptions = await async_get_all_descriptions(hass)
    connection.send_message(messages.result_message(msg["id"], descriptions))


@callback
@decorators.websocket_command({vol.Required("type"): "get_config"})
def handle_get_config(hass, connection, msg):
    """Handle get config command."""
    connection.send_message(messages.result_message(msg["id"], hass.config.as_dict()))


@decorators.websocket_command({vol.Required("type"): "manifest/list"})
@decorators.async_response
async def handle_manifest_list(hass, connection, msg):
    """Handle integrations command."""
    integrations = await asyncio.gather(
        *[
            async_get_integration(hass, domain)
            for domain in hass.config.components
            # Filter out platforms.
            if "." not in domain
        ]
    )
    connection.send_result(
        msg["id"], [integration.manifest for integration in integrations]
    )


@decorators.websocket_command(
    {vol.Required("type"): "manifest/get", vol.Required("integration"): str}
)
@decorators.async_response
async def handle_manifest_get(hass, connection, msg):
    """Handle integrations command."""
    try:
        integration = await async_get_integration(hass, msg["integration"])
        connection.send_result(msg["id"], integration.manifest)
    except IntegrationNotFound:
        connection.send_error(msg["id"], const.ERR_NOT_FOUND, "Integration not found")


@callback
@decorators.websocket_command({vol.Required("type"): "ping"})
def handle_ping(hass, connection, msg):
    """Handle ping command."""
    connection.send_message(pong_message(msg["id"]))


@callback
@decorators.websocket_command(
    {
        vol.Required("type"): "render_template",
        vol.Required("template"): cv.template,
        vol.Optional("entity_ids"): cv.entity_ids,
        vol.Optional("variables"): dict,
    }
)
def handle_render_template(hass, connection, msg):
    """Handle render_template command."""
    template = msg["template"]
    template.hass = hass

    variables = msg.get("variables")

    @callback
    def _template_listener(event, template, last_result, result):
        if isinstance(result, TemplateError):
            _LOGGER.error(
                "TemplateError('%s') " "while processing template '%s'",
                result,
                template,
            )

            result = None

        connection.send_message(messages.event_message(msg["id"], {"result": result}))

    info = async_track_template_result(hass, template, _template_listener, variables)

    connection.subscriptions[msg["id"]] = info.async_remove

    connection.send_result(msg["id"])

    hass.loop.call_soon_threadsafe(info.async_refresh)


@callback
@decorators.websocket_command(
    {vol.Required("type"): "entity/source", vol.Optional("entity_id"): [cv.entity_id]}
)
def handle_entity_source(hass, connection, msg):
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

        connection.send_message(messages.result_message(msg["id"], sources))
        return

    sources = {}

    for entity_id in msg["entity_id"]:
        if not entity_perm(entity_id, "read"):
            raise Unauthorized(
                context=connection.context(msg),
                permission=POLICY_READ,
                perm_category=CAT_ENTITIES,
            )

        source = raw_sources.get(entity_id)

        if source is None:
            connection.send_error(msg["id"], ERR_NOT_FOUND, "Entity not found")
            return

        sources[entity_id] = source

    connection.send_result(msg["id"], sources)


@callback
@decorators.websocket_command(
    {
        vol.Required("type"): "subscribe_trigger",
        vol.Required("trigger"): cv.TRIGGER_SCHEMA,
        vol.Optional("variables"): dict,
    }
)
@decorators.require_admin
@decorators.async_response
async def handle_subscribe_trigger(hass, connection, msg):
    """Handle subscribe trigger command."""
    # Circular dep
    # pylint: disable=import-outside-toplevel
    from homeassistant.helpers import trigger

    trigger_config = await trigger.async_validate_trigger_config(hass, msg["trigger"])

    @callback
    def forward_triggers(variables, context=None):
        """Forward events to websocket."""
        connection.send_message(
            messages.event_message(
                msg["id"], {"variables": variables, "context": context}
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
async def handle_test_condition(hass, connection, msg):
    """Handle test condition command."""
    # Circular dep
    # pylint: disable=import-outside-toplevel
    from homeassistant.helpers import condition

    check_condition = await condition.async_from_config(hass, msg["condition"])
    connection.send_result(
        msg["id"], {"result": check_condition(hass, msg.get("variables"))}
    )
