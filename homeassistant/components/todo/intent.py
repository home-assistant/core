"""Intents for the todo integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent

from . import DOMAIN, TodoItem, TodoItemStatus, TodoListEntity

INTENT_LIST_ADD_ITEM = "HassListAddItem"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the todo intents."""
    intent.async_register(hass, ListAddItemIntent())


class ListAddItemIntent(intent.IntentHandler):
    """Handle ListAddItem intents."""

    intent_type = INTENT_LIST_ADD_ITEM
    description = "Add item to a todo list"
    slot_schema = {"item": cv.string, "name": cv.string}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass

        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"]
        list_name = slots["name"]["value"]

        component: EntityComponent[TodoListEntity] = hass.data[DOMAIN]
        target_list: TodoListEntity | None = None

        # Find matching list
        for list_state in intent.async_match_states(
            hass, name=list_name, domains=[DOMAIN]
        ):
            target_list = component.get_entity(list_state.entity_id)
            if target_list is not None:
                break

        if target_list is None:
            raise intent.IntentHandleError(f"No to-do list: {list_name}")

        assert target_list is not None

        # Add to list
        await target_list.async_create_todo_item(
            TodoItem(summary=item, status=TodoItemStatus.NEEDS_ACTION)
        )

        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.ACTION_DONE
        return response
