"""Support to manage a ais tts."""
import logging
import uuid

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import http, websocket_api
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import HTTP_BAD_REQUEST, HTTP_NOT_FOUND
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json

from .const import DOMAIN

ATTR_NAME = "name"

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: {}}, extra=vol.ALLOW_EXTRA)
EVENT = "aistts_list_updated"
ITEM_UPDATE_SCHEMA = vol.Schema({"complete": bool, ATTR_NAME: str})
PERSISTENCE = ".dom/.aistts.json"

SERVICE_ADD_ITEM = "add_item"
SERVICE_COMPLETE_ITEM = "complete_item"

SERVICE_ITEM_SCHEMA = vol.Schema({vol.Required(ATTR_NAME): vol.Any(None, cv.string)})

WS_TYPE_AISTTS_ITEMS = "aistts/items"
WS_TYPE_AISTTS_ADD_ITEM = "aistts/items/add"
WS_TYPE_AISTTS_UPDATE_ITEM = "aistts/items/update"
WS_TYPE_AISTTS_CLEAR_ITEMS = "aistts/items/clear"

SCHEMA_WEBSOCKET_ITEMS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_AISTTS_ITEMS}
)

SCHEMA_WEBSOCKET_ADD_ITEM = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_AISTTS_ADD_ITEM,
        vol.Required("name"): str,
        vol.Required("pitch"): str,
        vol.Required("rate"): str,
        vol.Required("language"): str,
        vol.Required("voice"): str,
    }
)

SCHEMA_WEBSOCKET_UPDATE_ITEM = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_AISTTS_UPDATE_ITEM,
        vol.Required("item_id"): str,
        vol.Optional("name"): str,
        vol.Optional("complete"): bool,
    }
)

SCHEMA_WEBSOCKET_CLEAR_ITEMS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_AISTTS_CLEAR_ITEMS}
)


async def async_setup(hass, config):
    """Initialize the AIS TTS"""

    if DOMAIN not in config:
        return True

    async def add_item_service(call):
        """Add an item with `name`."""
        data = hass.data[DOMAIN]
        name = call.data.get(ATTR_NAME)
        pitch = all.data.get("pitch")
        rate = all.data.get("rate")
        language = all.data.get("language")
        voice = all.data.get("voice")
        if name is not None:
            data.async_add(name, pitch, rate, language, voice)

    async def complete_item_service(call):
        """Mark the item provided via `name` as completed."""
        data = hass.data[DOMAIN]
        name = call.data.get(ATTR_NAME)
        if name is None:
            return
        try:
            item = [item for item in data.items if item["name"] == name][0]
        except IndexError:
            _LOGGER.error("Removing of item failed: %s cannot be found", name)
        else:
            data.async_update(item["id"], {"name": name, "complete": True})

    data = hass.data[DOMAIN] = AisTtsData(hass)
    await data.async_load()

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_ITEM, add_item_service, schema=SERVICE_ITEM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_COMPLETE_ITEM, complete_item_service, schema=SERVICE_ITEM_SCHEMA
    )

    hass.http.register_view(AisTtsView)
    hass.http.register_view(CreateAisTtsItemView)
    hass.http.register_view(UpdateAisTtsItemView)
    hass.http.register_view(ClearCompletedItemsView)

    hass.components.frontend.async_register_built_in_panel(
        "aistts",
        require_admin=True,
        sidebar_title="AIS TTS",
        sidebar_icon="mdi:bullhorn-outline",
        update=True,
    )

    hass.components.websocket_api.async_register_command(
        WS_TYPE_AISTTS_ITEMS, websocket_handle_items, SCHEMA_WEBSOCKET_ITEMS
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_AISTTS_ADD_ITEM, websocket_handle_add, SCHEMA_WEBSOCKET_ADD_ITEM
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_AISTTS_UPDATE_ITEM,
        websocket_handle_update,
        SCHEMA_WEBSOCKET_UPDATE_ITEM,
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_AISTTS_CLEAR_ITEMS,
        websocket_handle_clear,
        SCHEMA_WEBSOCKET_CLEAR_ITEMS,
    )

    return True


class AisTtsData:
    """Class to hold ais tts data."""

    def __init__(self, hass):
        """Initialize the ais tts."""
        self.hass = hass
        self.items = []

    @callback
    def async_add(self, name, pitch, rate, language, voice):
        """Add a ais tts item."""
        item = {
            "name": name,
            "pitch": pitch,
            "rate": rate,
            "language": language,
            "voice": voice,
            "id": uuid.uuid4().hex,
            "complete": False,
        }
        self.items.append(item)
        self.hass.async_add_job(self.save)
        return item

    @callback
    def async_update(self, item_id, info):
        """Update a ais tts item."""
        item = next((itm for itm in self.items if itm["id"] == item_id), None)

        if item is None:
            raise KeyError

        info = ITEM_UPDATE_SCHEMA(info)
        item.update(info)
        self.hass.async_add_job(self.save)
        return item

    @callback
    def async_clear_completed(self):
        """Clear completed items."""
        self.items = [itm for itm in self.items if not itm["complete"]]
        self.hass.async_add_job(self.save)

    async def async_load(self):
        """Load items."""

        def load():
            """Load the items synchronously."""
            return load_json(self.hass.config.path(PERSISTENCE), default=[])

        self.items = await self.hass.async_add_executor_job(load)

    def save(self):
        """Save the items."""
        save_json(self.hass.config.path(PERSISTENCE), self.items)


class AisTtsView(http.HomeAssistantView):
    """View to retrieve ais tts content."""

    url = "/api/aistts"
    name = "api:aistts"

    @callback
    def get(self, request):
        """Retrieve ais tts items."""
        return self.json(request.app["hass"].data[DOMAIN].items)


class UpdateAisTtsItemView(http.HomeAssistantView):
    """View to retrieve ais tts content."""

    url = "/api/aistts/item/{item_id}"
    name = "api:aistts:item:id"

    async def post(self, request, item_id):
        """Update a ais tts item."""
        data = await request.json()

        try:
            item = request.app["hass"].data[DOMAIN].async_update(item_id, data)
            request.app["hass"].bus.async_fire(EVENT)
            return self.json(item)
        except KeyError:
            return self.json_message("Item not found", HTTP_NOT_FOUND)
        except vol.Invalid:
            return self.json_message("Item not found", HTTP_BAD_REQUEST)


class CreateAisTtsItemView(http.HomeAssistantView):
    """View to retrieve ais tts content."""

    url = "/api/aistts/item"
    name = "api:aistts:item"

    @RequestDataValidator(vol.Schema({vol.Required("name"): str}))
    async def post(self, request, data):
        """Create a new ais tts item."""
        item = request.app["hass"].data[DOMAIN].async_add(data["name"])
        request.app["hass"].bus.async_fire(EVENT)
        return self.json(item)


class ClearCompletedItemsView(http.HomeAssistantView):
    """View to retrieve ais tts content."""

    url = "/api/aistts/clear_completed"
    name = "api:aistts:clear_completed"

    @callback
    def post(self, request):
        """Retrieve if API is running."""
        hass = request.app["hass"]
        hass.data[DOMAIN].async_clear_completed()
        hass.bus.async_fire(EVENT)
        return self.json_message("Cleared completed items.")


@callback
def websocket_handle_items(hass, connection, msg):
    """Handle get ais tts items."""
    connection.send_message(
        websocket_api.result_message(msg["id"], hass.data[DOMAIN].items)
    )


@callback
def websocket_handle_add(hass, connection, msg):
    """Handle add item to ais tts."""
    item = hass.data[DOMAIN].async_add(
        msg["name"], msg["pitch"], msg["rate"], msg["language"], msg["voice"]
    )
    hass.bus.async_fire(EVENT, {"action": "add", "item": item})
    connection.send_message(websocket_api.result_message(msg["id"], item))


@websocket_api.async_response
async def websocket_handle_update(hass, connection, msg):
    """Handle update ais tts item."""
    msg_id = msg.pop("id")
    item_id = msg.pop("item_id")
    msg.pop("type")
    data = msg

    try:
        item = hass.data[DOMAIN].async_update(item_id, data)
        hass.bus.async_fire(EVENT, {"action": "update", "item": item})
        connection.send_message(websocket_api.result_message(msg_id, item))
    except KeyError:
        connection.send_message(
            websocket_api.error_message(msg_id, "item_not_found", "Item not found")
        )


@callback
def websocket_handle_clear(hass, connection, msg):
    """Handle clearing ais tts items."""
    hass.data[DOMAIN].async_clear_completed()
    hass.bus.async_fire(EVENT, {"action": "clear"})
    connection.send_message(websocket_api.result_message(msg["id"]))
