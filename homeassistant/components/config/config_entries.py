"""Http views to control the config manager."""
import aiohttp.web_exceptions
import voluptuous as vol
import voluptuous_serialize

from homeassistant import config_entries, data_entry_flow
from homeassistant.auth.permissions.const import CAT_CONFIG_ENTRIES, POLICY_EDIT
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import HTTP_FORBIDDEN, HTTP_NOT_FOUND
from homeassistant.core import callback
from homeassistant.exceptions import Unauthorized
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.data_entry_flow import (
    FlowManagerIndexView,
    FlowManagerResourceView,
)
from homeassistant.loader import async_get_config_flows


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

    hass.components.websocket_api.async_register_command(config_entry_update)
    hass.components.websocket_api.async_register_command(config_entries_progress)
    hass.components.websocket_api.async_register_command(system_options_list)
    hass.components.websocket_api.async_register_command(system_options_update)
    hass.components.websocket_api.async_register_command(ignore_config_flow)

    return True


def _prepare_json(result):
    """Convert result for JSON."""
    if result["type"] != data_entry_flow.RESULT_TYPE_FORM:
        return result

    data = result.copy()

    schema = data["data_schema"]
    if schema is None:
        data["data_schema"] = []
    else:
        data["data_schema"] = voluptuous_serialize.convert(
            schema, custom_serializer=cv.custom_serializer
        )

    return data


class ConfigManagerEntryIndexView(HomeAssistantView):
    """View to get available config entries."""

    url = "/api/config/config_entries/entry"
    name = "api:config:config_entries:entry"

    async def get(self, request):
        """List available config entries."""
        hass = request.app["hass"]

        return self.json(
            [entry_json(entry) for entry in hass.config_entries.async_entries()]
        )


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
            return self.json_message("Invalid entry specified", HTTP_NOT_FOUND)

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

        try:
            result = await hass.config_entries.async_reload(entry_id)
        except config_entries.OperationNotAllowed:
            return self.json_message("Entry cannot be reloaded", HTTP_FORBIDDEN)
        except config_entries.UnknownEntry:
            return self.json_message("Invalid entry specified", HTTP_NOT_FOUND)

        return self.json({"require_restart": not result})


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
        return await super().post(request)

    def _prepare_result_json(self, result):
        """Convert result to JSON."""
        if result["type"] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            return super()._prepare_result_json(result)

        data = result.copy()
        data["result"] = data["result"].entry_id
        data.pop("data")
        return data


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
        if result["type"] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            return super()._prepare_result_json(result)

        data = result.copy()
        data["result"] = data["result"].entry_id
        data.pop("data")
        return data


class ConfigManagerAvailableFlowView(HomeAssistantView):
    """View to query available flows."""

    url = "/api/config/config_entries/flow_handlers"
    name = "api:config:config_entries:flow_handlers"

    async def get(self, request):
        """List available flow handlers."""
        hass = request.app["hass"]
        return self.json(await async_get_config_flows(hass))


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
def config_entries_progress(hass, connection, msg):
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


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {"type": "config_entries/system_options/list", "entry_id": str}
)
async def system_options_list(hass, connection, msg):
    """List all system options for a config entry."""
    entry_id = msg["entry_id"]
    entry = hass.config_entries.async_get_entry(entry_id)

    if entry:
        connection.send_result(msg["id"], entry.system_options.as_dict())


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        "type": "config_entries/system_options/update",
        "entry_id": str,
        vol.Optional("disable_new_entities"): bool,
    }
)
async def system_options_update(hass, connection, msg):
    """Update config entry system options."""
    changes = dict(msg)
    changes.pop("id")
    changes.pop("type")
    entry_id = changes.pop("entry_id")
    entry = hass.config_entries.async_get_entry(entry_id)

    if entry is None:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "Config entry not found"
        )
        return

    hass.config_entries.async_update_entry(entry, system_options=changes)
    connection.send_result(msg["id"], entry.system_options.as_dict())


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {"type": "config_entries/update", "entry_id": str, vol.Optional("title"): str}
)
async def config_entry_update(hass, connection, msg):
    """Update config entry."""
    changes = dict(msg)
    changes.pop("id")
    changes.pop("type")
    entry_id = changes.pop("entry_id")

    entry = hass.config_entries.async_get_entry(entry_id)

    if entry is None:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "Config entry not found"
        )
        return

    hass.config_entries.async_update_entry(entry, **changes)
    connection.send_result(msg["id"], entry_json(entry))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {"type": "config_entries/ignore_flow", "flow_id": str, "title": str}
)
async def ignore_config_flow(hass, connection, msg):
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
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "Config entry not found"
        )
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


@callback
def entry_json(entry: config_entries.ConfigEntry) -> dict:
    """Return JSON value of a config entry."""
    handler = config_entries.HANDLERS.get(entry.domain)
    supports_options = (
        # Guard in case handler is no longer registered (custom compnoent etc)
        handler is not None
        # pylint: disable=comparison-with-callable
        and handler.async_get_options_flow
        != config_entries.ConfigFlow.async_get_options_flow
    )
    return {
        "entry_id": entry.entry_id,
        "domain": entry.domain,
        "title": entry.title,
        "source": entry.source,
        "state": entry.state,
        "connection_class": entry.connection_class,
        "supports_options": supports_options,
        "supports_unload": entry.supports_unload,
    }
