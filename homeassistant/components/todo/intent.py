"""Intents for the todo integration."""

from __future__ import annotations

from typing import ClassVar

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import TodoItem, TodoItemStatus, TodoListEntity
from .const import DATA_COMPONENT, DOMAIN

INTENT_LIST_ADD_ITEM = "HassListAddItem"
INTENT_LIST_COMPLETE_ITEM = "HassListCompleteItem"
INTENT_LIST_REMOVE_ITEM = "HassListRemoveItem"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the todo intents."""
    intent.async_register(hass, ListAddItemIntent())
    intent.async_register(hass, ListCompleteItemIntent())
    intent.async_register(hass, ListRemoveItemIntent())


class ListBaseItent(intent.IntentHandle):
    """Base class for toto intents."""

    slot_schema: ClassVar[dict] = {
        vol.Required("item"): intent.non_empty_string,
        vol.Required("name"): intent.non_empty_string,
    }
    platforms: ClassVar[dict] = {DOMAIN}

    def _get_params(self, intent_obj: intent.Intent) -> tuple[str, str]:
        """Validate and return intent params."""
        slots = self.async_validate_slots(intent_obj.slots)

        item = slots["item"]["value"].strip()
        list_name = slots["name"]["value"]

        return item, list_name

    def _get_target_list(
        self, intent_obj: intent.Intent, list_name: str
    ) -> TodoListEntity:
        """Return the requested todo list."""
        hass = intent_obj.hass

        target_list: TodoListEntity | None = None

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

        return target_list

    def _create_response(
        self, intent_obj: intent.Intent, list_name: str, list_id: str
    ) -> intent.IntentResponse:
        """Builds the intent response."""
        response: intent.IntentResponse = intent_obj.create_response()
        response.async_set_results(
            [
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    name=list_name,
                    id=list_id,
                )
            ]
        )
        return response


class ListAddItemIntent(ListBaseItent):
    """Handle ListAddItem intents."""

    intent_type = INTENT_LIST_ADD_ITEM
    description = "Add item to a todo list"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        item, list_name = self._get_params(intent_obj)
        target_list = self._get_target_list(intent_obj, list_name)

        # Add to list
        await target_list.async_create_todo_item(
            TodoItem(summary=item, status=TodoItemStatus.NEEDS_ACTION)
        )

        return self._create_response(intent_obj, list_name, target_list.entity_id)


class ListCompleteItemIntent(ListBaseItent):
    """Handle ListCompleteItem intents."""

    intent_type = INTENT_LIST_COMPLETE_ITEM
    description = "Complete item on a todo list"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        item, list_name = self._get_params(intent_obj)
        target_list = self._get_target_list(intent_obj, list_name)

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

        return self._create_response(intent_obj, list_name, target_list.entity_id)


class ListRemoveItemIntent(ListBaseItent):
    """Handle LisRemoveItemIntent intents."""

    intent_type = INTENT_LIST_REMOVE_ITEM
    description = "Remove one or more items from a todo list"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        item, list_name = self._get_params(intent_obj)
        target_list = self._get_target_list(intent_obj, list_name)

        # Find items in list
        matching_item_uids = [
            todo_item.uid
            for todo_item in target_list.todo_items or ()
            if item in (todo_item.uid, todo_item.summary) and todo_item.uid is not None
        ]
        if not matching_item_uids:
            raise intent.IntentHandleError(
                f"Item '{item}' not found on list", "item_not_found"
            )

        # Remove items
        await target_list.async_delete_todo_items(matching_item_uids)

        return self._create_response(intent_obj, list_name, target_list.entity_id)
