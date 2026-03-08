"""Intents for the todo integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import TodoItem, TodoItemStatus, TodoListEntity
from .const import DATA_COMPONENT, DOMAIN

INTENT_LIST_ADD_ITEM = "HassListAddItem"
INTENT_LIST_COMPLETE_ITEM = "HassListCompleteItem"
INTENT_LIST_REMOVE_ITEM = "HassListRemoveItem"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the todo intent handlers."""
    intent.async_register(hass, ListAddItemIntentHandler())
    intent.async_register(hass, ListCompleteItemIntentHandler())
    intent.async_register(hass, ListRemoveItemIntentHandler())


class ListBaseIntentHandler(intent.IntentHandler):
    """Base class for toto intent handlers."""

    slot_schema = {
        vol.Required("item"): intent.non_empty_string,
        vol.Required("name"): intent.non_empty_string,
    }
    platforms = {DOMAIN}

    async def _async_do_handle(self, target_list: TodoListEntity, item: str) -> None:
        """Execute action specific to this intent handler."""
        raise NotImplementedError

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass

        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"].strip()
        list_name = slots["name"]["value"]

        target_list: TodoListEntity | None = None

        # Find matching list
        match_constraints = intent.MatchTargetsConstraints(
            name=list_name, domains=[DOMAIN], assistant=intent_obj.assistant
        )
        match_result = intent.async_match_targets(hass, match_constraints)
        if not match_result.is_match:
            raise intent.MatchFailedError(
                result=match_result, constraints=match_constraints
            )

        target_list = hass.data[DATA_COMPONENT].get_entity(
            match_result.states[0].entity_id
        )
        if target_list is None:
            raise intent.IntentHandleError(
                f"No to-do list: {list_name}", "list_not_found"
            )

        # Execute specific action
        await self._async_do_handle(target_list, item)

        # Build intent response
        response: intent.IntentResponse = intent_obj.create_response()
        response.async_set_results(
            [
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    name=list_name,
                    id=target_list.entity_id,
                )
            ]
        )
        return response


class ListAddItemIntentHandler(ListBaseIntentHandler):
    """Handle ListAddItem intents."""

    intent_type = INTENT_LIST_ADD_ITEM
    description = "Add item to a todo list"

    async def _async_do_handle(self, target_list: TodoListEntity, item: str) -> None:
        """Execute action specific to this intent handler."""

        # Add to list
        await target_list.async_create_todo_item(
            TodoItem(summary=item, status=TodoItemStatus.NEEDS_ACTION)
        )


class ListCompleteItemIntentHandler(ListBaseIntentHandler):
    """Handle ListCompleteItem intents."""

    intent_type = INTENT_LIST_COMPLETE_ITEM
    description = "Complete item on a todo list"

    async def _async_do_handle(self, target_list: TodoListEntity, item: str) -> None:
        """Execute action specific to this intent handler."""

        # Find item in list
        matching_item = None
        for todo_item in target_list.todo_items or ():
            if (
                item in (todo_item.uid, todo_item.summary)
                and todo_item.status == TodoItemStatus.NEEDS_ACTION
            ):
                matching_item = todo_item
                break
        if not matching_item or not matching_item.uid:
            raise intent.IntentHandleError(
                f"Item '{item}' not found on list", "item_not_found"
            )

        # Mark as completed
        await target_list.async_update_todo_item(
            TodoItem(
                uid=matching_item.uid,
                summary=matching_item.summary,
                status=TodoItemStatus.COMPLETED,
            )
        )


class ListRemoveItemIntentHandler(ListBaseIntentHandler):
    """Handle LisRemoveItemIntent intents."""

    intent_type = INTENT_LIST_REMOVE_ITEM
    description = "Remove one or more items from a todo list"

    async def _async_do_handle(self, target_list: TodoListEntity, item: str) -> None:
        """Execute action specific to this intent handler."""

        # Find item in list
        matching_item = None
        for todo_item in target_list.todo_items or ():
            if item in (todo_item.uid, todo_item.summary):
                matching_item = todo_item
                break
        if not matching_item or not matching_item.uid:
            raise intent.IntentHandleError(
                f"Item '{item}' not found on list", "item_not_found"
            )

        # Remove items
        await target_list.async_delete_todo_items(uids=[matching_item.uid])
