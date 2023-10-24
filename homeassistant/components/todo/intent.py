"""Intents for the todo integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.shopping_list import EVENT_SHOPPING_LIST_UPDATED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent

from . import DOMAIN, TodoItem, TodoListEntity

INTENT_ADD_ITEM = "HassShoppingListAddItem"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the todo intents."""
    intent.async_register(hass, AddItemIntent())


class AddItemIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_ADD_ITEM
    slot_schema = {"item": cv.string, vol.Optional("list"): cv.string}

    async def async_handle(self, intent_obj: intent.Intent):
        """Handle the intent."""
        hass = intent_obj.hass

        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"]

        component: EntityComponent[TodoListEntity] = hass.data[DOMAIN]
        list_entities: list[TodoListEntity] = list(component.entities)
        if not list_entities:
            raise intent.IntentHandleError("No list entities")

        target_list: TodoListEntity | None = None

        if "list" in slots:
            # Add to a list by name
            list_name = slots["list"]["value"]

            # Find matching list
            matching_states = intent.async_match_states(
                hass, name=list_name, domains=[DOMAIN]
            )
            for list_state in matching_states:
                for maybe_list in list_entities:
                    if maybe_list.entity_id == list_state.entity_id:
                        target_list = maybe_list
                        break

                if target_list is not None:
                    break

            if target_list is None:
                raise intent.IntentHandleError(f"No list named {list_name}")
        else:
            # Add to the first list
            target_list = list_entities[0]

        assert target_list is not None

        # Add to list
        await target_list.async_create_todo_item(TodoItem(item))

        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.ACTION_DONE
        intent_obj.hass.bus.async_fire(EVENT_SHOPPING_LIST_UPDATED)
        return response
