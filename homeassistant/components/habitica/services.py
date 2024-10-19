"""Actions for the Habitica integration."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from http import HTTPStatus
from typing import TYPE_CHECKING
import uuid

from aiohttp import ClientResponseError
import voluptuous as vol

from homeassistant.components.todo import ATTR_DESCRIPTION, ATTR_RENAME
from homeassistant.const import ATTR_DATE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import (
    ATTR_ADD_CHECKLIST_ITEM,
    ATTR_ALIAS,
    ATTR_CLEAR_DATE,
    ATTR_CLEAR_REMINDER,
    ATTR_CONFIG_ENTRY,
    ATTR_COST,
    ATTR_COUNTER_DOWN,
    ATTR_COUNTER_UP,
    ATTR_FREQUENCY,
    ATTR_INTERVAL,
    ATTR_PRIORITY,
    ATTR_REMINDER,
    ATTR_REMINDER_TIME,
    ATTR_REMOVE_CHECKLIST_ITEM,
    ATTR_REMOVE_REMINDER,
    ATTR_REMOVE_REMINDER_TIME,
    ATTR_REMOVE_TAG,
    ATTR_REPEAT,
    ATTR_REPEAT_MONTHLY,
    ATTR_SCORE_CHECKLIST_ITEM,
    ATTR_START_DATE,
    ATTR_STREAK,
    ATTR_TAG,
    ATTR_TASK,
    ATTR_UNSCORE_CHECKLIST_ITEM,
    ATTR_UP_DOWN,
    DOMAIN,
    PRIORITIES,
    SERVICE_UPDATE_DAILY,
    SERVICE_UPDATE_HABIT,
    SERVICE_UPDATE_REWARD,
    SERVICE_UPDATE_TODO,
    WEEK_DAYS,
)
from .types import HabiticaConfigEntry
from .util import get_config_entry, lookup_task, to_date

SERVICE_UPDATE_TASK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector(),
        vol.Required(ATTR_TASK): cv.string,
        vol.Optional(ATTR_RENAME): cv.string,
        vol.Optional(ATTR_DESCRIPTION): cv.string,
        vol.Optional(ATTR_TAG): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_REMOVE_TAG): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_ALIAS): vol.All(
            cv.string, cv.matches_regex("^[a-zA-Z0-9-_]+$")
        ),
        vol.Optional(ATTR_PRIORITY): vol.All(cv.string, vol.In(set(PRIORITIES.keys()))),
        vol.Optional(ATTR_DATE): cv.date,
        vol.Optional(ATTR_CLEAR_DATE): cv.boolean,
        vol.Optional(ATTR_REMINDER): vol.All(cv.ensure_list, [cv.datetime]),
        vol.Optional(ATTR_REMINDER_TIME): vol.All(cv.ensure_list, [cv.time]),
        vol.Optional(ATTR_REMOVE_REMINDER): vol.All(cv.ensure_list, [cv.datetime]),
        vol.Optional(ATTR_REMOVE_REMINDER_TIME): vol.All(cv.ensure_list, [cv.time]),
        vol.Optional(ATTR_CLEAR_REMINDER): cv.boolean,
        vol.Optional(ATTR_COST): vol.Coerce(float),
        vol.Optional(ATTR_ADD_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_REMOVE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_SCORE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_UNSCORE_CHECKLIST_ITEM): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_UP_DOWN): vol.All(
            cv.ensure_list, [vol.In({"positive", "negative"})]
        ),
        vol.Optional(ATTR_START_DATE): cv.date,
        vol.Optional(ATTR_FREQUENCY): vol.All(
            cv.string, vol.In({"daily", "weekly", "monthly", "yearly"})
        ),
        vol.Optional(ATTR_INTERVAL): int,
        vol.Optional(ATTR_REPEAT): vol.All(cv.ensure_list, [vol.In(WEEK_DAYS)]),
        vol.Optional(ATTR_REPEAT_MONTHLY): vol.All(
            cv.string, vol.In({"day_of_month", "day_of_week"})
        ),
        vol.Optional(ATTR_COUNTER_UP): int,
        vol.Optional(ATTR_COUNTER_DOWN): int,
        vol.Optional(ATTR_STREAK): int,
    }
)


def async_setup_services(hass: HomeAssistant) -> None:  # noqa: C901
    """Set up services for Habitica integration."""

    async def update_task(call: ServiceCall) -> ServiceResponse:  # noqa: C901
        """Update task action."""
        entry: HabiticaConfigEntry = get_config_entry(
            hass, call.data[ATTR_CONFIG_ENTRY]
        )
        coordinator = entry.runtime_data
        await coordinator.async_refresh()

        current_task = lookup_task(
            coordinator.data.tasks, call.data[ATTR_TASK], call.service
        )
        task_id = current_task["id"]
        data = {}

        if rename := call.data.get(ATTR_RENAME):
            data.update({"text": rename})

        if description := call.data.get(ATTR_DESCRIPTION):
            data.update({"notes": description})

        if priority := call.data.get(ATTR_PRIORITY):
            data.update({"priority": PRIORITIES[priority]})

        if due_date := call.data.get(ATTR_DATE):
            data.update({"date": (datetime.combine(due_date, time()).isoformat())})

        if call.data.get(ATTR_CLEAR_DATE):
            data.update({"date": None})

        tags = call.data.get(ATTR_TAG)
        remove_tags = call.data.get(ATTR_REMOVE_TAG)

        if tags or remove_tags:
            update_tags = set(
                next(
                    (
                        task.get("tags", [])
                        for task in coordinator.data.tasks
                        if task["id"] == task_id
                    ),
                    [],
                )
            )
            user_tags = {
                tag["name"].lower(): tag["id"]
                for tag in coordinator.data.user.get("tags", [])
            }

            if tags:
                # Creates new tag if it doesn't exist
                try:
                    update_tags.update(
                        {
                            user_tags.get(tag_name.lower())
                            or (await coordinator.api.tags.post(name=tag_name)).get(
                                "id"
                            )
                            for tag_name in tags
                        }
                    )
                except ClientResponseError as e:
                    if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                        raise ServiceValidationError(
                            translation_domain=DOMAIN,
                            translation_key="setup_rate_limit_exception",
                        ) from e
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="service_call_exception",
                    ) from e

            if remove_tags:
                update_tags.difference_update(
                    {
                        user_tags[tag_name.lower()]
                        for tag_name in remove_tags
                        if tag_name.lower() in user_tags
                    }
                )

            data.update({"tags": list(update_tags)})

        if alias := call.data.get(ATTR_ALIAS):
            data.update({"alias": alias})

        if cost := call.data.get(ATTR_COST):
            data.update({"value": cost})

        add_checklist_item = call.data.get(ATTR_ADD_CHECKLIST_ITEM)
        remove_checklist_item = call.data.get(ATTR_REMOVE_CHECKLIST_ITEM)
        score_checklist_item = call.data.get(ATTR_SCORE_CHECKLIST_ITEM, [])
        unscore_checklist_item = call.data.get(ATTR_UNSCORE_CHECKLIST_ITEM, [])

        if (
            add_checklist_item
            or remove_checklist_item
            or score_checklist_item
            or unscore_checklist_item
        ):
            checklist = current_task.get("checklist", [])

            if add_checklist_item:
                checklist.extend(
                    {"completed": False, "id": str(uuid.uuid4()), "text": item}
                    for item in add_checklist_item
                    if not any(i["text"] == item for i in checklist)
                )
            if remove_checklist_item:
                checklist = [
                    item
                    for item in checklist
                    if item["text"] not in remove_checklist_item
                ]
            if score_checklist_item or unscore_checklist_item:
                checklist = [
                    {
                        **item,
                        "completed": (
                            True
                            if item["text"] in score_checklist_item
                            else False
                            if item["text"] in unscore_checklist_item
                            else item["completed"]
                        ),
                    }
                    for item in checklist
                ]

            data.update({"checklist": checklist})

        if frequency := call.data.get(ATTR_FREQUENCY):
            data.update({"frequency": frequency})
        if interval := call.data.get(ATTR_INTERVAL):
            data.update({"everyX": interval})
        if up_down := call.data.get(ATTR_UP_DOWN):
            data.update(
                {
                    "up": "positive" in up_down,
                    "down": "negative" in up_down,
                }
            )
        if start_date := call.data.get(ATTR_START_DATE):
            data.update(
                {"startDate": (datetime.combine(start_date, time()).isoformat())}
            )

        if repeat := call.data.get(ATTR_REPEAT):
            if (frequency or current_task.get("frequency")) == "weekly":
                data.update({"repeat": {d: d in repeat for d in WEEK_DAYS}})
            else:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="frequency_not_weekly",
                )
        if repeat_monthly := call.data.get(ATTR_REPEAT_MONTHLY):
            if (frequency or current_task.get("frequency")) != "monthly":
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="frequency_not_monthly",
                )

            current_start_date = start_date or to_date(current_task["startDate"])
            if not current_start_date:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="frequency_not_monthly",
                )

            if TYPE_CHECKING:
                assert isinstance(current_start_date, date)
            if repeat_monthly == "day_of_week":
                weekday = current_start_date.weekday()
                data.update(
                    {
                        "weeksOfMonth": (current_start_date.day - 1) // 7,
                        "repeat": {
                            day: i == weekday for i, day in enumerate(WEEK_DAYS)
                        },
                        "daysOfMonth": [],
                    }
                )
            else:
                data.update({"daysOfMonth": current_start_date.day, "weeksOfMonth": []})

        if reminder := call.data.get(ATTR_REMINDER):
            existing_reminder_datetimes = {
                datetime.fromisoformat(r["time"]).replace(tzinfo=None)
                for r in current_task.get("reminders", [])
            }

            data.update(
                {
                    "reminders": (
                        [
                            {
                                "id": str(uuid.uuid4()),
                                "time": r.isoformat(),
                            }
                            for r in reminder
                            if r not in existing_reminder_datetimes
                        ]
                        + current_task.get("reminders", [])
                    )
                }
            )
        if reminder_time := call.data.get(ATTR_REMINDER_TIME):
            existing_reminder_times = {
                datetime.fromisoformat(r["time"])
                .time()
                .replace(microsecond=0, second=0)
                for r in current_task.get("reminders", [])
            }

            data.update(
                {
                    "reminders": (
                        [
                            {
                                "id": str(uuid.uuid4()),
                                "startDate": "",
                                "time": datetime.combine(
                                    date.today(), r, tzinfo=UTC
                                ).isoformat(),
                            }
                            for r in reminder_time
                            if r not in existing_reminder_times
                        ]
                        + current_task.get("reminders", [])
                    )
                }
            )
        if remove_reminder := call.data.get(ATTR_REMOVE_REMINDER):
            reminders = list(
                filter(
                    lambda r: datetime.fromisoformat(r["time"]).replace(tzinfo=None)
                    not in remove_reminder,
                    current_task.get("reminders", []),
                )
            )
            data.update({"reminders": reminders})
        if remove_reminder_time := call.data.get(ATTR_REMOVE_REMINDER_TIME):
            reminders = list(
                filter(
                    lambda r: datetime.fromisoformat(r["time"])
                    .time()
                    .replace(second=0, microsecond=0)
                    not in remove_reminder_time,
                    current_task.get("reminders", []),
                )
            )
            data.update({"reminders": reminders})

        if call.data.get(ATTR_CLEAR_REMINDER):
            data.update({"reminders": []})

        if streak := call.data.get(ATTR_STREAK):
            data.update({"streak": streak})
        if counter_up := call.data.get(ATTR_COUNTER_UP):
            data.update({"counterUp": counter_up})
        if counter_down := call.data.get(ATTR_COUNTER_DOWN):
            data.update({"counterDown": counter_down})
        try:
            return await coordinator.api.tasks[task_id].put(**data)
        except ClientResponseError as e:
            if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="setup_rate_limit_exception",
                ) from e
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e

    for service in (
        SERVICE_UPDATE_DAILY,
        SERVICE_UPDATE_HABIT,
        SERVICE_UPDATE_REWARD,
        SERVICE_UPDATE_TODO,
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            update_task,
            schema=SERVICE_UPDATE_TASK_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
