"""Support to interact with Remember The Milk."""

from __future__ import annotations

from typing import Any

from rtmapi import Rtm, RtmRequestFailedException

from homeassistant.const import CONF_ID, CONF_NAME, STATE_OK
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity import Entity

from .const import LOGGER
from .storage import RememberTheMilkConfiguration


class RememberTheMilkEntity(Entity):
    """Representation of an interface to Remember The Milk."""

    def __init__(
        self,
        name: str,
        api_key: str,
        shared_secret: str,
        token: str,
        rtm_config: RememberTheMilkConfiguration,
    ) -> None:
        """Create new instance of Remember The Milk component."""
        self._name = name
        self._api_key = api_key
        self._shared_secret = shared_secret
        self._token = token
        self._rtm_config = rtm_config
        self._rtm_api = Rtm(api_key, shared_secret, "delete", token)
        self._token_valid = False

    async def check_token(self, hass: HomeAssistant) -> None:
        """Check if the API token is still valid.

        If it is not valid any more, delete it from the configuration. This
        will trigger a new authentication process.
        """
        valid = await hass.async_add_executor_job(self._rtm_api.token_valid)
        if valid:
            self._token_valid = True
            return

        LOGGER.error(
            "Token for account %s is invalid. You need to register again!",
            self.name,
        )
        self._rtm_config.delete_token(self._name)
        self._token_valid = False

    async def create_task(self, call: ServiceCall) -> None:
        """Create a new task on Remember The Milk.

        You can use the smart syntax to define the attributes of a new task,
        e.g. "my task #some_tag ^today" will add tag "some_tag" and set the
        due date to today.
        """
        try:
            task_name = call.data[CONF_NAME]
            hass_id = call.data.get(CONF_ID)
            rtm_id = None
            if hass_id is not None:
                rtm_id = self._rtm_config.get_rtm_id(self._name, hass_id)

            if rtm_id is None:
                result = await self.hass.async_add_executor_job(
                    self._add_task,
                    task_name,
                )
                LOGGER.debug(
                    "Created new task '%s' in account %s", task_name, self.name
                )
                if hass_id is not None:
                    self._rtm_config.set_rtm_id(
                        self._name,
                        hass_id,
                        result.list.id,
                        result.list.taskseries.id,
                        result.list.taskseries.task.id,
                    )
            else:
                await self.hass.async_add_executor_job(
                    self._rename_task,
                    rtm_id,
                    task_name,
                )
                LOGGER.debug(
                    "Updated task with id '%s' in account %s to name %s",
                    hass_id,
                    self.name,
                    task_name,
                )
        except RtmRequestFailedException as rtm_exception:
            LOGGER.error(
                "Error creating new Remember The Milk task for account %s: %s",
                self._name,
                rtm_exception,
            )

    def _add_task(self, task_name: str) -> Any:
        """Add a task."""
        result = self._rtm_api.rtm.timelines.create()
        timeline = result.timeline.value
        return self._rtm_api.rtm.tasks.add(
            timeline=timeline,
            name=task_name,
            parse="1",
        )

    def _rename_task(self, rtm_id: tuple[str, str, str], task_name: str) -> None:
        """Rename a task."""
        result = self._rtm_api.rtm.timelines.create()
        timeline = result.timeline.value
        self._rtm_api.rtm.tasks.setName(
            name=task_name,
            list_id=rtm_id[0],
            taskseries_id=rtm_id[1],
            task_id=rtm_id[2],
            timeline=timeline,
        )

    async def complete_task(self, call: ServiceCall) -> None:
        """Complete a task that was previously created by this component."""
        hass_id = call.data[CONF_ID]
        rtm_id = self._rtm_config.get_rtm_id(self._name, hass_id)
        if rtm_id is None:
            LOGGER.error(
                (
                    "Could not find task with ID %s in account %s. "
                    "So task could not be closed"
                ),
                hass_id,
                self._name,
            )
            return
        try:
            await self.hass.async_add_executor_job(self._complete_task, rtm_id)
        except RtmRequestFailedException as rtm_exception:
            LOGGER.error(
                "Error creating new Remember The Milk task for account %s: %s",
                self._name,
                rtm_exception,
            )
            return

        self._rtm_config.delete_rtm_id(self._name, hass_id)
        LOGGER.debug("Completed task with id %s in account %s", hass_id, self._name)

    def _complete_task(self, rtm_id: tuple[str, str, str]) -> None:
        """Complete a task."""
        result = self._rtm_api.rtm.timelines.create()
        timeline = result.timeline.value
        self._rtm_api.rtm.tasks.complete(
            list_id=rtm_id[0],
            taskseries_id=rtm_id[1],
            task_id=rtm_id[2],
            timeline=timeline,
        )

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if not self._token_valid:
            return "API token invalid"
        return STATE_OK
