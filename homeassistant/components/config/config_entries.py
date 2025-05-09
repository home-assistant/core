"""Http views to control the config manager."""

from __future__ import annotations

from collections.abc import Callable
from http import HTTPStatus
from typing import Any, NoReturn

from aiohttp import web
import aiohttp.web_exceptions
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.auth.permissions.const import CAT_CONFIG_ENTRIES, POLICY_EDIT
from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_HASS, HomeAssistantView, require_admin
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import DependencyError, Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.data_entry_flow import (
    FlowManagerIndexView,
    FlowManagerResourceView,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.json import json_fragment
from homeassistant.loader import (
    Integration,
    IntegrationNotFound,
    async_get_config_flows,
    async_get_integrations,
    async_get_loaded_integration,
)


@callback
def async_setup(hass: HomeAssistant) -> bool:
    """Enable the Home Assistant views."""
    hass.http.register_view(ConfigManagerEntryIndexView)
    hass.http.register_view(ConfigManagerEntryResourceView)
    hass.http.register_view(ConfigManagerEntryResourceReloadView)
    hass.http.register_view(ConfigManagerFlowIndexView(hass.config_entries.flow))
    hass.http.register_view(ConfigManagerFlowResourceView(hass.config_entries.flow))
    hass.http.register_view(ConfigManagerAvailableFlowView)

    hass.http.register_view(OptionManagerFlowIndexView(hass.config_entries.options))
    hass.http.register_view(OptionManagerFlowResourceView(hass.config_entries.options))

    hass.http.register_view(
        SubentryManagerFlowIndexView(hass.config_entries.subentries)
    )
    hass.http.register_view(
        SubentryManagerFlowResourceView(hass.config_entries.subentries)
    )

    websocket_api.async_register_command(hass, config_entries_get)
    websocket_api.async_register_command(hass, config_entry_disable)
    websocket_api.async_register_command(hass, config_entry_get_single)
    websocket_api.async_register_command(hass, config_entry_update)
    websocket_api.async_register_command(hass, config_entries_subscribe)
    websocket_api.async_register_command(hass, config_entries_flow_progress)
    websocket_api.async_register_command(hass, config_entries_flow_subscribe)
    websocket_api.async_register_command(hass, ignore_config_flow)

    websocket_api.async_register_command(hass, config_subentry_delete)
    websocket_api.async_register_command(hass, config_subentry_list)

    return True


class ConfigManagerEntryIndexView(HomeAssistantView):
    """View to get available config entries."""

    url = "/api/config/config_entries/entry"
    name = "api:config:config_entries:entry"

    async def get(self, request: web.Request) -> web.Response:
        """List available config entries."""
        hass = request.app[KEY_HASS]
        domain = None
        if "domain" in request.query:
            domain = request.query["domain"]
        type_filter = None
        if "type" in request.query:
            type_filter = [request.query["type"]]
        fragments = await _async_matching_config_entries_json_fragments(
            hass, type_filter, domain
        )
        return self.json(fragments)


class ConfigManagerEntryResourceView(HomeAssistantView):
    """View to interact with a config entry."""

    url = "/api/config/config_entries/entry/{entry_id}"
    name = "api:config:config_entries:entry:resource"

    async def delete(self, request: web.Request, entry_id: str) -> web.Response:
        """Delete a config entry."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(config_entry_id=entry_id, permission="remove")

        hass = request.app[KEY_HASS]

        try:
            result = await hass.config_entries.async_remove(entry_id)
        except config_entries.UnknownEntry:
            return self.json_message("Invalid entry specified", HTTPStatus.NOT_FOUND)

        return self.json(result)


class ConfigManagerEntryResourceReloadView(HomeAssistantView):
    """View to reload a config entry."""

    url = "/api/config/config_entries/entry/{entry_id}/reload"
    name = "api:config:config_entries:entry:resource:reload"

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        """Reload a config entry."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(config_entry_id=entry_id, permission="remove")

        hass = request.app[KEY_HASS]
        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            return self.json_message("Invalid entry specified", HTTPStatus.NOT_FOUND)
        assert isinstance(entry, config_entries.ConfigEntry)

        try:
            await hass.config_entries.async_reload(entry_id)
        except config_entries.OperationNotAllowed:
            return self.json_message("Entry cannot be reloaded", HTTPStatus.FORBIDDEN)

        return self.json({"require_restart": not entry.state.recoverable})


def _prepare_config_flow_result_json(
    result: data_entry_flow.FlowResult,
    prepare_result_json: Callable[
        [data_entry_flow.FlowResult], data_entry_flow.FlowResult
    ],
) -> data_entry_flow.FlowResult:
    """Convert result to JSON."""
    if result["type"] != data_entry_flow.FlowResultType.CREATE_ENTRY:
        return prepare_result_json(result)

    data = result.copy()
    entry: config_entries.ConfigEntry = data["result"]
    data["result"] = entry.as_json_fragment
    data.pop("data")
    data.pop("context")
    return data


class ConfigManagerFlowIndexView(
    FlowManagerIndexView[config_entries.ConfigEntriesFlowManager]
):
    """View to create config flows."""

    url = "/api/config/config_entries/flow"
    name = "api:config:config_entries:flow"

    async def get(self, request: web.Request) -> NoReturn:
        """Not implemented."""
        raise aiohttp.web_exceptions.HTTPMethodNotAllowed("GET", ["POST"])

    @require_admin(perm_category=CAT_CONFIG_ENTRIES, permission="add")
    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("handler"): vol.Any(str, list),
                vol.Optional("show_advanced_options", default=False): cv.boolean,
                vol.Optional("entry_id"): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        )
    )
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Initialize a POST request for a config entry flow."""
        return await self._post_impl(request, data)

    async def _post_impl(
        self, request: web.Request, data: dict[str, Any]
    ) -> web.Response:
        """Handle a POST request for a config entry flow."""
        try:
            return await super()._post_impl(request, data)
        except DependencyError as exc:
            return web.Response(
                text=f"Failed dependencies {', '.join(exc.failed_dependencies)}",
                status=HTTPStatus.BAD_REQUEST,
            )

    def get_context(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return context."""
        context = super().get_context(data)
        context["source"] = config_entries.SOURCE_USER
        if entry_id := data.get("entry_id"):
            context["source"] = config_entries.SOURCE_RECONFIGURE
            context["entry_id"] = entry_id
        return context

    def _prepare_result_json(
        self, result: data_entry_flow.FlowResult
    ) -> data_entry_flow.FlowResult:
        """Convert result to JSON."""
        return _prepare_config_flow_result_json(result, super()._prepare_result_json)


class ConfigManagerFlowResourceView(
    FlowManagerResourceView[config_entries.ConfigEntriesFlowManager]
):
    """View to interact with the flow manager."""

    url = "/api/config/config_entries/flow/{flow_id}"
    name = "api:config:config_entries:flow:resource"

    @require_admin(perm_category=CAT_CONFIG_ENTRIES, permission="add")
    async def get(self, request: web.Request, /, flow_id: str) -> web.Response:
        """Get the current state of a data_entry_flow."""
        return await super().get(request, flow_id)

    @require_admin(perm_category=CAT_CONFIG_ENTRIES, permission="add")
    async def post(self, request: web.Request, flow_id: str) -> web.Response:
        """Handle a POST request."""
        return await super().post(request, flow_id)

    def _prepare_result_json(
        self, result: data_entry_flow.FlowResult
    ) -> data_entry_flow.FlowResult:
        """Convert result to JSON."""
        return _prepare_config_flow_result_json(result, super()._prepare_result_json)


class ConfigManagerAvailableFlowView(HomeAssistantView):
    """View to query available flows."""

    url = "/api/config/config_entries/flow_handlers"
    name = "api:config:config_entries:flow_handlers"

    async def get(self, request: web.Request) -> web.Response:
        """List available flow handlers."""
        hass = request.app[KEY_HASS]
        kwargs: dict[str, Any] = {}
        if "type" in request.query:
            kwargs["type_filter"] = request.query["type"]
        return self.json(await async_get_config_flows(hass, **kwargs))


class OptionManagerFlowIndexView(
    FlowManagerIndexView[config_entries.OptionsFlowManager]
):
    """View to create option flows."""

    url = "/api/config/config_entries/options/flow"
    name = "api:config:config_entries:option:flow"

    @require_admin(perm_category=CAT_CONFIG_ENTRIES, permission=POLICY_EDIT)
    async def post(self, request: web.Request) -> web.Response:
        """Handle a POST request.

        handler in request is entry_id.
        """
        return await super().post(request)


class OptionManagerFlowResourceView(
    FlowManagerResourceView[config_entries.OptionsFlowManager]
):
    """View to interact with the option flow manager."""

    url = "/api/config/config_entries/options/flow/{flow_id}"
    name = "api:config:config_entries:options:flow:resource"

    @require_admin(perm_category=CAT_CONFIG_ENTRIES, permission=POLICY_EDIT)
    async def get(self, request: web.Request, /, flow_id: str) -> web.Response:
        """Get the current state of a data_entry_flow."""
        return await super().get(request, flow_id)

    @require_admin(perm_category=CAT_CONFIG_ENTRIES, permission=POLICY_EDIT)
    async def post(self, request: web.Request, flow_id: str) -> web.Response:
        """Handle a POST request."""
        return await super().post(request, flow_id)


class SubentryManagerFlowIndexView(
    FlowManagerIndexView[config_entries.ConfigSubentryFlowManager]
):
    """View to create subentry flows."""

    url = "/api/config/config_entries/subentries/flow"
    name = "api:config:config_entries:subentries:flow"

    @require_admin(perm_category=CAT_CONFIG_ENTRIES, permission=POLICY_EDIT)
    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("handler"): vol.All(vol.Coerce(tuple), (str, str)),
                vol.Optional("show_advanced_options", default=False): cv.boolean,
            },
            extra=vol.ALLOW_EXTRA,
        )
    )
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Handle a POST request.

        handler in request is [entry_id, subentry_type].
        """
        return await super()._post_impl(request, data)

    def get_context(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return context."""
        context = super().get_context(data)
        context["source"] = config_entries.SOURCE_USER
        if subentry_id := data.get("subentry_id"):
            context["source"] = config_entries.SOURCE_RECONFIGURE
            context["subentry_id"] = subentry_id
        return context


class SubentryManagerFlowResourceView(
    FlowManagerResourceView[config_entries.ConfigSubentryFlowManager]
):
    """View to interact with the subentry flow manager."""

    url = "/api/config/config_entries/subentries/flow/{flow_id}"
    name = "api:config:config_entries:subentries:flow:resource"

    @require_admin(perm_category=CAT_CONFIG_ENTRIES, permission=POLICY_EDIT)
    async def get(self, request: web.Request, /, flow_id: str) -> web.Response:
        """Get the current state of a data_entry_flow."""
        return await super().get(request, flow_id)

    @require_admin(perm_category=CAT_CONFIG_ENTRIES, permission=POLICY_EDIT)
    async def post(self, request: web.Request, flow_id: str) -> web.Response:
        """Handle a POST request."""
        return await super().post(request, flow_id)


@websocket_api.require_admin
@websocket_api.websocket_command({"type": "config_entries/flow/progress"})
def config_entries_flow_progress(
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
            if flw["context"]["source"]
            not in (config_entries.SOURCE_RECONFIGURE, config_entries.SOURCE_USER)
        ],
    )


@websocket_api.require_admin
@websocket_api.websocket_command({"type": "config_entries/flow/subscribe"})
def config_entries_flow_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to non user created flows being initiated or removed.

    When initiating the subscription, the current flows are sent to the client.

    Example of a non-user initiated flow is a discovered Hue hub that
    requires user interaction to finish setup.
    """

    @callback
    def async_on_flow_init_remove(change_type: str, flow_id: str) -> None:
        """Forward config entry state events to websocket."""
        if change_type == "removed":
            connection.send_message(
                websocket_api.event_message(
                    msg["id"],
                    [{"type": change_type, "flow_id": flow_id}],
                )
            )
            return
        # change_type == "added"
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                [
                    {
                        "type": change_type,
                        "flow_id": flow_id,
                        "flow": hass.config_entries.flow.async_get(flow_id),
                    }
                ],
            )
        )

    connection.subscriptions[msg["id"]] = hass.config_entries.flow.async_subscribe_flow(
        async_on_flow_init_remove
    )
    connection.send_message(
        websocket_api.event_message(
            msg["id"],
            [
                {"type": None, "flow_id": flw["flow_id"], "flow": flw}
                for flw in hass.config_entries.flow.async_progress()
                if flw["context"]["source"]
                not in (
                    config_entries.SOURCE_RECONFIGURE,
                    config_entries.SOURCE_USER,
                )
            ],
        )
    )
    connection.send_result(msg["id"])


def send_entry_not_found(
    connection: websocket_api.ActiveConnection, msg_id: int
) -> None:
    """Send Config entry not found error."""
    connection.send_error(msg_id, websocket_api.ERR_NOT_FOUND, "Config entry not found")


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
        "type": "config_entries/get_single",
        "entry_id": str,
    }
)
@websocket_api.async_response
async def config_entry_get_single(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update config entry."""
    entry = get_entry(hass, connection, msg["entry_id"], msg["id"])
    if entry is None:
        return

    result = {"config_entry": entry.as_json_fragment}
    connection.send_result(msg["id"], result)


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
        "config_entry": entry.as_json_fragment,
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

    context = config_entries.ConfigFlowContext(source=config_entries.SOURCE_IGNORE)
    if "discovery_key" in flow["context"]:
        context["discovery_key"] = flow["context"]["discovery_key"]
    await hass.config_entries.flow.async_init(
        flow["handler"],
        context=context,
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
    fragments = await _async_matching_config_entries_json_fragments(
        hass, msg.get("type_filter"), msg.get("domain")
    )
    connection.send_result(msg["id"], fragments)


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

    @callback
    def async_forward_config_entry_changes(
        change: config_entries.ConfigEntryChange, entry: config_entries.ConfigEntry
    ) -> None:
        """Forward config entry state events to websocket."""
        if type_filter:
            integration = async_get_loaded_integration(hass, entry.domain)
            if integration.integration_type not in type_filter:
                return

        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                [
                    {
                        "type": change,
                        "entry": entry.as_json_fragment,
                    }
                ],
            )
        )

    current_entries = await _async_matching_config_entries_json_fragments(
        hass, type_filter, None
    )
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


async def _async_matching_config_entries_json_fragments(
    hass: HomeAssistant, type_filter: list[str] | None, domain: str | None
) -> list[json_fragment]:
    """Return matching config entries by type and/or domain."""
    if domain:
        entries = hass.config_entries.async_entries(domain)
    else:
        entries = hass.config_entries.async_entries()

    if not type_filter:
        return [entry.as_json_fragment for entry in entries]

    integrations: dict[str, Integration] = {}
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
    filter_is_not_helper = type_filter != ["helper"]
    filter_set = set(type_filter)
    return [
        entry.as_json_fragment
        for entry in entries
        # If the filter is not 'helper', we still include the integration
        # even if its not returned from async_get_integrations for backwards
        # compatibility.
        if (
            (integration := integrations.get(entry.domain))
            and integration.integration_type in filter_set
        )
        or (filter_is_not_helper and entry.domain not in integrations)
    ]


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "config_entries/subentries/list",
        "entry_id": str,
    }
)
@websocket_api.async_response
async def config_subentry_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List subentries of a config entry."""
    entry = get_entry(hass, connection, msg["entry_id"], msg["id"])
    if entry is None:
        return

    result = [
        {
            "subentry_id": subentry.subentry_id,
            "subentry_type": subentry.subentry_type,
            "title": subentry.title,
            "unique_id": subentry.unique_id,
        }
        for subentry in entry.subentries.values()
    ]
    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "config_entries/subentries/delete",
        "entry_id": str,
        "subentry_id": str,
    }
)
@websocket_api.async_response
async def config_subentry_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete a subentry of a config entry."""
    entry = get_entry(hass, connection, msg["entry_id"], msg["id"])
    if entry is None:
        return

    try:
        hass.config_entries.async_remove_subentry(entry, msg["subentry_id"])
    except config_entries.UnknownSubEntry:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "Config subentry not found"
        )
        return

    connection.send_result(msg["id"])
