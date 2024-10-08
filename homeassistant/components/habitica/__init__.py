"""The habitica integration."""

from datetime import datetime, time
from http import HTTPStatus
import uuid

from aiohttp import ClientResponseError
from habitipy.aio import HabitipyAsync
import voluptuous as vol

from homeassistant.components.todo import ATTR_DESCRIPTION, ATTR_RENAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    APPLICATION_NAME,
    ATTR_DATE,
    CONF_API_KEY,
    CONF_NAME,
    CONF_URL,
    CONF_VERIFY_SSL,
    Platform,
    __version__,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.helpers.typing import ConfigType

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
    ATTR_PRIORITY,
    ATTR_REMINDER,
    ATTR_REMOVE_CHECKLIST_ITEM,
    ATTR_REMOVE_REMINDER,
    ATTR_REMOVE_TAG,
    ATTR_SCORE_CHECKLIST_ITEM,
    ATTR_TAG,
    ATTR_TASK,
    ATTR_UNSCORE_CHECKLIST_ITEM,
    ATTR_UP_DOWN,
    CONF_API_USER,
    DEVELOPER_ID,
    DOMAIN,
    PRIORITIES,
    SERVICE_UPDATE_DAILY,
    SERVICE_UPDATE_HABIT,
    SERVICE_UPDATE_REWARD,
    SERVICE_UPDATE_TODO,
)
from .coordinator import HabiticaDataUpdateCoordinator
from .services import async_setup_services
from .types import HabiticaConfigEntry
from .util import get_config_entry, lookup_task

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TODO,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Habitica service."""

    async_setup_services(hass)

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

        if reminder := call.data.get(ATTR_REMINDER):
            existing_reminder_times = {
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

        if call.data.get(ATTR_CLEAR_REMINDER):
            data.update({"reminders": []})

        if date := call.data.get(ATTR_DATE):
            data.update({"date": (datetime.combine(date, time()).isoformat())})

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
        if up_down := call.data.get(ATTR_UP_DOWN):
            data.update(
                {
                    "up": "positive" in up_down,
                    "down": "negative" in up_down,
                }
            )

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

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: HabiticaConfigEntry
) -> bool:
    """Set up habitica from a config entry."""

    class HAHabitipyAsync(HabitipyAsync):
        """Closure API class to hold session."""

        def __call__(self, **kwargs):
            return super().__call__(websession, **kwargs)

        def _make_headers(self) -> dict[str, str]:
            headers = super()._make_headers()
            headers.update(
                {"x-client": f"{DEVELOPER_ID} - {APPLICATION_NAME} {__version__}"}
            )
            return headers

    websession = async_get_clientsession(
        hass, verify_ssl=config_entry.data.get(CONF_VERIFY_SSL, True)
    )

    api = await hass.async_add_executor_job(
        HAHabitipyAsync,
        {
            "url": config_entry.data[CONF_URL],
            "login": config_entry.data[CONF_API_USER],
            "password": config_entry.data[CONF_API_KEY],
        },
    )
    try:
        user = await api.user.get(userFields="profile")
    except ClientResponseError as e:
        if e.status == HTTPStatus.TOO_MANY_REQUESTS:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="setup_rate_limit_exception",
            ) from e
        raise ConfigEntryNotReady(e) from e

    if not config_entry.data.get(CONF_NAME):
        name = user["profile"]["name"]
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_NAME: name},
        )

    coordinator = HabiticaDataUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
