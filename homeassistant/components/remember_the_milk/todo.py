from rtmapi import Rtm, RtmRequestFailedException

from homeassistant.components.remember_the_milk import (
    DOMAIN as REMEMBER_THE_MILK_DOMAIN,
    SERVICE_SCHEMA_CREATE_TASK,
)
from homeassistant.components.todo import (
    TodoItem,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    name = entry.data["name"]
    api_key = entry.data["api_key"]
    shared_secret = entry.data["shared_secret"]
    token = entry.data["token"]
    coordinator = RememberTheMilkCoordinator(name, api_key, shared_secret, token)

    async_add_entities([(RememberTheMilkTodoListEntity(hass, coordinator, name))])


class RememberTheMilkTodoListEntity(TodoListEntity):
    """Representation of a RememberTheMilk Todo list."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, hass: HomeAssistant, coordinator, title) -> None:
        """Initialize entity."""
        self.coordinator = coordinator

        self._attr_name = title
        self._attr_unique_id = title

        async def create_task(call: ServiceCall):
            name = call.data["name"]
            task_id = call.data["task_id"] if "task_id" in call.data else None
            await self.async_create_todo_item(TodoItem(name, uid=task_id))

        hass.services.async_register(
            REMEMBER_THE_MILK_DOMAIN,
            f"{title}_create_task",
            create_task,
            SERVICE_SCHEMA_CREATE_TASK,
        )

    async def async_create_todo_item(self, item: TodoItem) -> None:
        def create_todo_item():
            self.coordinator.upsert_item(item.summary, item.uid)

        await self.hass.async_add_executor_job(create_todo_item)


class RememberTheMilkCoordinator:
    def __init__(
        self, name: str, api_key: str, shared_secret: str, token: str = ""
    ) -> None:
        self.api = Rtm(api_key, shared_secret, "write", token=token)

    def check_token(self) -> bool:
        return self.api.token_valid()

    def authenticate_desktop(self) -> (str, str):
        try:
            return self.api.authenticate_desktop()
        except RtmRequestFailedException as e:
            # TODO karel: if it's an invalid key, go back to the user input step with error on api_key field
            raise e

    def get_token(self, frob):
        success = self.api.retrieve_token(frob)
        # TODO: error handling if not success
        return self.api.token

    def upsert_item(self, title, uid):
        if uid is not None:
            # TODO: support updates
            raise Exception("updating not supported yet")

        timeline_result = self.api.rtm.timelines.create()
        timeline = timeline_result.timeline.value

        self.api.rtm.tasks.add(name=title, timeline=timeline, parse="true")

    def complete_item(self, uid):
        # TODO implement complete_item but this requires some json storage like the old implementation did
        raise Exception("not implemented yet")
