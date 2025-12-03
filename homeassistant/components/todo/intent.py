"""Intents for the todo integration."""

from __future__ import annotations

import datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent

from . import TodoItem, TodoItemStatus, TodoListEntity
from .const import DATA_COMPONENT, DOMAIN

INTENT_LIST_ADD_ITEM = "HassListAddItem"
INTENT_LIST_COMPLETE_ITEM = "HassListCompleteItem"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the todo intents."""
    intent.async_register(hass, ListAddItemIntent())
    intent.async_register(hass, ListCompleteItemIntent())


class TodoItemDueDay(StrEnum):
    """Day value for list add item intent."""

    TODAY = "today"
    TOMORROW = "tomorrow"
    MONDAY = "mon"
    TUESDAY = "tue"
    WEDNESDAY = "wed"
    THURSDAY = "thu"
    FRIDAY = "fri"
    SATURDAY = "sat"
    SUNDAY = "sun"


ENUM_TO_WEEKDAY = {
    TodoItemDueDay.MONDAY: 0,
    TodoItemDueDay.TUESDAY: 1,
    TodoItemDueDay.WEDNESDAY: 2,
    TodoItemDueDay.THURSDAY: 3,
    TodoItemDueDay.FRIDAY: 4,
    TodoItemDueDay.SATURDAY: 5,
    TodoItemDueDay.SUNDAY: 6,
}


class ListAddItemIntent(intent.IntentHandler):
    """Handle ListAddItem intents."""

    intent_type = INTENT_LIST_ADD_ITEM
    description = "Add item to a todo list"
    slot_schema = {
        vol.Required("item"): intent.non_empty_string,
        vol.Required("name"): intent.non_empty_string,
        # absolute due datetime
        vol.Optional("due_day"): vol.In([d.value for d in TodoItemDueDay]),
        vol.Optional("due_hour"): cv.positive_int,
        vol.Optional("due_minute"): cv.positive_int,
        # relative due datetime
        vol.Optional("due_day_offset"): cv.positive_int,
        vol.Optional("due_hour_offset"): cv.positive_int,
        vol.Optional("due_minute_offset"): cv.positive_int,
    }
    platforms = {DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass

        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"].strip()
        list_name = slots["name"]["value"]

        due_day: TodoItemDueDay | None = None
        if "due_day" in slots:
            due_day = slots["due_day"]["value"]
        due_hour: int | None = None
        if "due_hour" in slots:
            due_hour = slots["due_hour"]["value"]
        due_minute: int | None = None
        if "due_minute" in slots:
            due_minute = slots["due_minute"]["value"]
        due_day_offset: int | None = None
        if "due_day_offset" in slots:
            due_day_offset = slots["due_day_offset"]["value"]
        due_hour_offset: int | None = None
        if "due_hour_offset" in slots:
            due_hour_offset = slots["due_hour_offset"]["value"]
        due_minute_offset: int | None = None
        if "due_minute_offset" in slots:
            due_minute_offset = slots["due_minute_offset"]["value"]

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

        # Compute due date
        due: datetime.date | datetime.datetime | None = None
        if due_day is not None or due_hour is not None:
            due = self.__get_absolute_due_date(
                hass.config.time_zone, due_day, due_hour, due_minute
            )
        elif (
            due_day_offset is not None
            or due_hour_offset is not None
            or due_minute_offset is not None
        ):
            due = self.__get_relative_due_date(
                hass.config.time_zone,
                due_day_offset,
                due_hour_offset,
                due_minute_offset,
            )

        # Add to list
        await target_list.async_create_todo_item(
            TodoItem(summary=item, status=TodoItemStatus.NEEDS_ACTION, due=due)
        )

        response: intent.IntentResponse = intent_obj.create_response()
        response.async_set_results(
            [
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    name=list_name,
                    id=match_result.states[0].entity_id,
                )
            ]
        )
        return response

    def __get_absolute_due_date(
        self,
        time_zone: str,
        day: TodoItemDueDay | None,
        hour: int | None,
        minute: int | None,
    ) -> datetime.date | datetime.datetime:
        """Gets the due date from the requested day + hour + minute."""
        now = datetime.datetime.now(ZoneInfo(time_zone))
        due = now

        # apply time
        if hour is not None:
            due = due.replace(hour=hour, minute=minute or 0, second=0, microsecond=0)

        # default day is today
        if day is None:
            day = TodoItemDueDay.TODAY

        # apply date
        match day:
            case TodoItemDueDay.TODAY:
                # no time provided: return only the date part
                if hour is None:
                    return due.date()
                # the time is passed: due is tomorrow
                if now > due:
                    due += datetime.timedelta(days=1)
                return due

            case TodoItemDueDay.TOMORROW:
                due += datetime.timedelta(days=1)
                # no time provided: return only the date part
                if hour is None:
                    return due.date()
                return due

            case _:
                # add the corresponding number of days
                due += datetime.timedelta(
                    days=(ENUM_TO_WEEKDAY[day] - due.weekday() + 7) % 7
                )
                # no time provided: return only the date part
                if hour is None:
                    # if same day: due is next week
                    if due.date() == now.date():
                        due += datetime.timedelta(weeks=1)
                    return due.date()
                # the time is passed: due is next week
                if now > due:
                    due += datetime.timedelta(weeks=1)
                return due

    def __get_relative_due_date(
        self,
        time_zone: str,
        day_offset: int | None,
        hour_offset: int | None,
        minute_offset: int | None,
    ) -> datetime.date | datetime.datetime:
        """Gets the due date from the requested offsets."""
        now = datetime.datetime.now(ZoneInfo(time_zone))
        due = now.replace(second=0, microsecond=0)

        # apply offsets
        if day_offset is not None:
            due += datetime.timedelta(days=day_offset)
        if hour_offset is not None:
            due += datetime.timedelta(hours=hour_offset)
        if minute_offset is not None:
            due += datetime.timedelta(minutes=minute_offset)

        # no time provided: return only the date part
        if day_offset is not None and hour_offset is None and minute_offset is None:
            return due.date()
        return due


class ListCompleteItemIntent(intent.IntentHandler):
    """Handle ListCompleteItem intents."""

    intent_type = INTENT_LIST_COMPLETE_ITEM
    description = "Complete item on a todo list"
    slot_schema = {
        vol.Required("item"): intent.non_empty_string,
        vol.Required("name"): intent.non_empty_string,
    }
    platforms = {DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass

        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"]
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

        response: intent.IntentResponse = intent_obj.create_response()
        response.async_set_results(
            [
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    name=list_name,
                    id=match_result.states[0].entity_id,
                )
            ]
        )
        return response
