"""Http views to control the config manager."""
from __future__ import annotations

from http import HTTPStatus
from typing import Any

from aiohttp import web
import aiohttp.web_exceptions
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.auth.permissions.const import CAT_CONFIG_ENTRIES, POLICY_EDIT
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import DependencyError, Unauthorized
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.data_entry_flow import (
    FlowManagerIndexView,
    FlowManagerResourceView,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.loader import (
    Integration,
    IntegrationNotFound,
    async_get_config_flows,
    async_get_integration,
    async_get_integrations,
)


async def async_setup(hass):
    """Enable the Home Assistant views."""
    hass.http.register_view(ConfigManagerEntryIndexView)
    hass.http.register_view(ConfigManagerEntryResourceView)
    hass.http.register_view(ConfigManagerEntryResourceReloadView)
    hass.http.register_view(ConfigManagerFlowIndexView(hass.config_entries.flow))
    hass.http.register_view(ConfigManagerFlowResourceView(hass.config_entries.flow))
    hass.http.register_view(ConfigManagerAvailableFlowView)

    hass.http.register_view(OptionManagerFlowIndexView(hass.config_entries.options))
    hass.http.register_view(OptionManagerFlowResourceView(hass.config_entries.options))

    websocket_api.async_register_command(hass, config_entries_get)
    websocket_api.async_register_command(hass, config_entry_disable)
    websocket_api.async_register_command(hass, config_entry_update)
    websocket_api.async_register_command(hass, config_entries_subscribe)
    websocket_api.async_register_command(hass, config_entries_progress)
    websocket_api.async_register_command(hass, ignore_config_flow)

    return True


class ConfigManagerEntryIndexView(HomeAssistantView):
    """View to get available config entries."""

    url = "/api/config/config_entries/entry"
    name = "api:config:config_entries:entry"

    async def get(self, request):
        """List available config entries."""
        hass: HomeAssistant = request.app["hass"]
        domain = None
        if "domain" in request.query:
            domain = request.query["domain"]
        type_filter = None
        if "type" in request.query:
            type_filter = [request.query["type"]]
        return self.json(await async_matching_config_entries(hass, type_filter, domain))


class ConfigManagerEntryResourceView(HomeAssistantView):
    """View to interact with a config entry."""

    url = "/api/config/config_entries/entry/{entry_id}"
    name = "api:config:config_entries:entry:resource"

    async def delete(self, request, entry_id):
        """Delete a config entry."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(config_entry_id=entry_id, permission="remove")

        hass = request.app["hass"]

        try:
            result = await hass.config_entries.async_remove(entry_id)
        except config_entries.UnknownEntry:
            return self.json_message("Invalid entry specified", HTTPStatus.NOT_FOUND)

        return self.json(result)


class ConfigManagerEntryResourceReloadView(HomeAssistantView):
    """View to reload a config entry."""

    url = "/api/config/config_entries/entry/{entry_id}/reload"
    name = "api:config:config_entries:entry:resource:reload"

    async def post(self, request, entry_id):
        """Reload a config entry."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(config_entry_id=entry_id, permission="remove")

        hass = request.app["hass"]
        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            return self.json_message("Invalid entry specified", HTTPStatus.NOT_FOUND)
        assert isinstance(entry, config_entries.ConfigEntry)

        try:
            await hass.config_entries.async_reload(entry_id)
        except config_entries.OperationNotAllowed:
            return self.json_message("Entry cannot be reloaded", HTTPStatus.FORBIDDEN)

        return self.json({"require_restart": not entry.state.recoverable})


def _prepare_config_flow_result_json(result, prepare_result_json):
    """Convert result to JSON."""
    if result["type"] != data_entry_flow.FlowResultType.CREATE_ENTRY:
        return prepare_result_json(result)

    data = result.copy()
    data["result"] = entry_json(result["result"])
    data.pop("data")
    data.pop("context")
    return data


class ConfigManagerFlowIndexView(FlowManagerIndexView):
    """View to create config flows."""

    url = "/api/config/config_entries/flow"
    name = "api:config:config_entries:flow"

    async def get(self, request):
        """Not implemented."""
        raise aiohttp.web_exceptions.HTTPMethodNotAllowed("GET", ["POST"])

    # pylint: disable=arguments-differ
    async def post(self, request):
        """Handle a POST request."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(perm_category=CAT_CONFIG_ENTRIES, permission="add")

        # pylint: disable=no-value-for-parameter
        try:
            return await super().post(request)
        except DependencyError as exc:
            return web.Response(
                text=f"Failed dependencies {', '.join(exc.failed_dependencies)}",
                status=HTTPStatus.BAD_REQUEST,
            )

    def _prepare_result_json(self, result):
        """Convert result to JSON."""
        return _prepare_config_flow_result_json(result, super()._prepare_result_json)


class ConfigManagerFlowResourceView(FlowManagerResourceView):
    """View to interact with the flow manager."""

    url = "/api/config/config_entries/flow/{flow_id}"
    name = "api:config:config_entries:flow:resource"

    async def get(self, request, flow_id):
        """Get the current state of a data_entry_flow."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(perm_category=CAT_CONFIG_ENTRIES, permission="add")

        return await super().get(request, flow_id)

    # pylint: disable=arguments-differ
    async def post(self, request, flow_id):
        """Handle a POST request."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(perm_category=CAT_CONFIG_ENTRIES, permission="add")

        # pylint: disable=no-value-for-parameter
        return await super().post(request, flow_id)

    def _prepare_result_json(self, result):
        """Convert result to JSON."""
        return _prepare_config_flow_result_json(result, super()._prepare_result_json)


class ConfigManagerAvailableFlowView(HomeAssistantView):
    """View to query available flows."""

    url = "/api/config/config_entries/flow_handlers"
    name = "api:config:config_entries:flow_handlers"

    async def get(self, request):
        """List available flow handlers."""
        hass = request.app["hass"]
        kwargs = {}
        if "type" in request.query:
            kwargs["type_filter"] = request.query["type"]
        return self.json(await async_get_config_flows(hass, **kwargs))


class OptionManagerFlowIndexView(FlowManagerIndexView):
    """View to create option flows."""

    url = "/api/config/config_entries/options/flow"
    name = "api:config:config_entries:option:flow"

    # pylint: disable=arguments-differ
    async def post(self, request):
        """Handle a POST request.

        handler in request is entry_id.
        """
        if not request["hass_user"].is_admin:
            raise Unauthorized(perm_category=CAT_CONFIG_ENTRIES, permission=POLICY_EDIT)

        # pylint: disable=no-value-for-parameter
        return await super().post(request)


class OptionManagerFlowResourceView(FlowManagerResourceView):
    """View to interact with the option flow manager."""

    url = "/api/config/config_entries/options/flow/{flow_id}"
    name = "api:config:config_entries:options:flow:resource"

    async def get(self, request, flow_id):
        """Get the current state of a data_entry_flow."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(perm_category=CAT_CONFIG_ENTRIES, permission=POLICY_EDIT)

        return await super().get(request, flow_id)

    # pylint: disable=arguments-differ
    async def post(self, request, flow_id):
        """Handle a POST request."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(perm_category=CAT_CONFIG_ENTRIES, permission=POLICY_EDIT)

        # pylint: disable=no-value-for-parameter
        return await super().post(request, flow_id)


@websocket_api.require_admin
@websocket_api.websocket_command({"type": "config_entries/flow/progress"})
def config_entries_progress(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List flows that are in progress but not started by a user.

    Example of a non-user initiated flow is a discovered Hue hub that
    requires user interaction to finish setup.
    """
    connection.send_result(
        msg["id"],
        [
            flw
            for flw in hass.config_entries.flow.async_progress()
            if flw["context"]["source"] != config_entries.SOURCE_USER
        ],
    )


def send_entry_not_found(
    connection: websocket_api.ActiveConnection, msg_id: int
) -> None:
    """Send Config entry not found error."""
    connection.send_error(
        msg_id, websocket_api.const.ERR_NOT_FOUND, "Config entry not found"
    )


def get_entry(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    entry_id: str,
    msg_id: int,
) -> config_entries.ConfigEntry | None:
    """Get entry, send error message if it doesn't exist."""
    if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
        send_entry_not_found(connection, msg_id)
    return entry


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "config_entries/update",
        "entry_id": str,
        vol.Optional("title"): str,
        vol.Optional("pref_disable_new_entities"): bool,
        vol.Optional("pref_disable_polling"): bool,
    }
)
@websocket_api.async_response
async def config_entry_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update config entry."""
    changes = dict(msg)
    changes.pop("id")
    changes.pop("type")
    changes.pop("entry_id")

    entry = get_entry(hass, connection, msg["entry_id"], msg["id"])
    if entry is None:
        return

    old_disable_polling = entry.pref_disable_polling

    hass.config_entries.async_update_entry(entry, **changes)

    result = {
        "config_entry": entry_json(entry),
        "require_restart": False,
    }

    initial_state = entry.state
    if (
        old_disable_polling != entry.pref_disable_polling
        and initial_state is config_entries.ConfigEntryState.LOADED
    ):
        if not await hass.config_entries.async_reload(entry.entry_id):
            result["require_restart"] = (
                entry.state is config_entries.ConfigEntryState.FAILED_UNLOAD
            )

    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "config_entries/disable",
        "entry_id": str,
        # We only allow setting disabled_by user via API.
        # No Enum support like this in voluptuous, use .value
        "disabled_by": vol.Any(config_entries.ConfigEntryDisabler.USER.value, None),
    }
)
@websocket_api.async_response
async def config_entry_disable(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Disable config entry."""
    if (disabled_by := msg["disabled_by"]) is not None:
        disabled_by = config_entries.ConfigEntryDisabler(disabled_by)

    success = False
    try:
        success = await hass.config_entries.async_set_disabled_by(
            msg["entry_id"], disabled_by
        )
    except config_entries.OperationNotAllowed:
        # Failed to unload the config entry
        pass
    except config_entries.UnknownEntry:
        send_entry_not_found(connection, msg["id"])
        return

    result = {"require_restart": not success}

    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {"type": "config_entries/ignore_flow", "flow_id": str, "title": str}
)
@websocket_api.async_response
async def ignore_config_flow(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Ignore a config flow."""
    flow = next(
        (
            flw
            for flw in hass.config_entries.flow.async_progress()
            if flw["flow_id"] == msg["flow_id"]
        ),
        None,
    )

    if flow is None:
        send_entry_not_found(connection, msg["id"])
        return

    if "unique_id" not in flow["context"]:
        connection.send_error(
            msg["id"], "no_unique_id", "Specified flow has no unique ID."
        )
        return

    await hass.config_entries.flow.async_init(
        flow["handler"],
        context={"source": config_entries.SOURCE_IGNORE},
        data={"unique_id": flow["context"]["unique_id"], "title": msg["title"]},
    )
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config_entries/get",
        vol.Optional("type_filter"): vol.All(cv.ensure_list, [str]),
        vol.Optional("domain"): str,
    }
)
@websocket_api.async_response
async def config_entries_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return matching config entries by type and/or domain."""
    connection.send_result(
        msg["id"],
        await async_matching_config_entries(
            hass, msg.get("type_filter"), msg.get("domain")
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config_entries/subscribe",
        vol.Optional("type_filter"): vol.All(cv.ensure_list, [str]),
    }
)
@websocket_api.async_response
async def config_entries_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to config entry updates."""
    type_filter = msg.get("type_filter")

    async def async_forward_config_entry_changes(
        change: config_entries.ConfigEntryChange, entry: config_entries.ConfigEntry
    ) -> None:
        """Forward config entry state events to websocket."""
        if type_filter:
            integration = await async_get_integration(hass, entry.domain)
            if integration.integration_type not in type_filter:
                return

        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                [
                    {
                        "type": change,
                        "entry": entry_json(entry),
                    }
                ],
            )
        )

    current_entries = await async_matching_config_entries(hass, type_filter, None)
    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass,
        config_entries.SIGNAL_CONFIG_ENTRY_CHANGED,
        async_forward_config_entry_changes,
    )
    connection.send_result(msg["id"])
    connection.send_message(
        websocket_api.event_message(
            msg["id"], [{"type": None, "entry": entry} for entry in current_entries]
        )
    )


async def async_matching_config_entries(
    hass: HomeAssistant, type_filter: list[str] | None, domain: str | None
) -> list[dict[str, Any]]:
    """Return matching config entries by type and/or domain."""
    kwargs = {}
    if domain:
        kwargs["domain"] = domain
    entries = hass.config_entries.async_entries(**kwargs)

    if not type_filter:
        return [entry_json(entry) for entry in entries]

    integrations = {}
    # Fetch all the integrations so we can check their type
    domains = {entry.domain for entry in entries}
    for domain_key, integration_or_exc in (
        await async_get_integrations(hass, domains)
    ).items():
        if isinstance(integration_or_exc, Integration):
            integrations[domain_key] = integration_or_exc
        elif not isinstance(integration_or_exc, IntegrationNotFound):
            raise integration_or_exc

    # Filter out entries that don't match the type filter
    # when only helpers are requested, also filter out entries
    # from unknown integrations. This prevent them from showing
    # up in the helpers UI.
    entries = [
        entry
        for entry in entries
        if (type_filter != ["helper"] and entry.domain not in integrations)
        or (
            entry.domain in integrations
            and integrations[entry.domain].integration_type in type_filter
        )
    ]

    return [entry_json(entry) for entry in entries]


@callback
def entry_json(entry: config_entries.ConfigEntry) -> dict:
    """Return JSON value of a config entry."""
    handler = config_entries.HANDLERS.get(entry.domain)
    # work out if handler has support for options flow
    supports_options = handler is not None and handler.async_supports_options_flow(
        entry
    )

    return {
        "entry_id": entry.entry_id,
        "domain": entry.domain,
        "title": entry.title,
        "source": entry.source,
        "state": entry.state.value,
        "supports_options": supports_options,
        "supports_remove_device": entry.supports_remove_device or False,
        "supports_unload": entry.supports_unload or False,
        "pref_disable_new_entities": entry.pref_disable_new_entities,
        "pref_disable_polling": entry.pref_disable_polling,
        "disabled_by": entry.disabled_by,
        "reason": entry.reason,
    }
