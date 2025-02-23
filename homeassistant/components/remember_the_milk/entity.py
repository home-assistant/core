"""Support to interact with Remember The Milk."""

from __future__ import annotations

from aiortm import AioRTMClient, AioRTMError, AuthError

from homeassistant.const import CONF_ID, CONF_NAME, STATE_OK
from homeassistant.core import ServiceCall
from homeassistant.helpers.entity import Entity

from .const import LOGGER
from .storage import RememberTheMilkConfiguration


class RememberTheMilkEntity(Entity):
    """Representation of an interface to Remember The Milk."""

    def __init__(
        self,
        name: str,
        client: AioRTMClient,
        rtm_config: RememberTheMilkConfiguration,
    ) -> None:
        """Create new instance of Remember The Milk component."""
        self._name = name
        self._rtm_config = rtm_config
        self._client = client
        self._token_valid = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await self.check_token()

    async def check_token(self) -> None:
        """Check if the API token is still valid.

        If it is not valid any more, delete it from the configuration. This
        will trigger a new authentication process.
        """
        try:
            await self._client.rtm.api.check_token()
        except AuthError as err:
            LOGGER.error(
                "Token for account %s is invalid. You need to register again: %s",
                self.name,
                err,
            )
        except AioRTMError as err:
            LOGGER.error(
                "Error checking token for account %s. You need to register again: %s",
                self.name,
                err,
            )
        else:
            self._token_valid = True
            return

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
                rtm_id = await self._add_task(task_name)
                LOGGER.debug(
                    "Created new task '%s' in account %s", task_name, self.name
                )
                if hass_id is not None:
                    self._rtm_config.set_rtm_id(
                        self._name,
                        hass_id,
                        rtm_id[0],
                        rtm_id[1],
                        rtm_id[2],
                    )
            else:
                await self._rename_task(rtm_id, task_name)
                LOGGER.debug(
                    "Updated task with id '%s' in account %s to name %s",
                    hass_id,
                    self.name,
                    task_name,
                )
        except AioRTMError as err:
            LOGGER.error(
                "Error creating new Remember The Milk task for account %s: %s",
                self._name,
                err,
            )

    async def _add_task(self, task_name: str) -> tuple[str, str, str]:
        """Add a task."""
        timeline_response = await self._client.rtm.timelines.create()
        timeline = timeline_response.timeline
        task_response = await self._client.rtm.tasks.add(
            timeline=timeline,
            name=task_name,
            parse=True,
        )
        task_list = task_response.task_list
        task_list_id = task_list.id
        task_series = task_list.taskseries[0]
        task_series_id = task_series.id
        task = task_series.task[0]
        task_id = task.id
        return (str(task_list_id), str(task_series_id), str(task_id))

    async def _rename_task(self, rtm_id: tuple[str, str, str], task_name: str) -> None:
        """Rename a task."""
        result = await self._client.rtm.timelines.create()
        timeline = result.timeline
        await self._client.rtm.tasks.set_name(
            name=task_name,
            list_id=int(rtm_id[0]),
            taskseries_id=int(rtm_id[1]),
            task_id=int(rtm_id[2]),
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
            await self._complete_task(rtm_id)
        except AioRTMError as err:
            LOGGER.error(
                "Error creating new Remember The Milk task for account %s: %s",
                self._name,
                err,
            )
            return

        self._rtm_config.delete_rtm_id(self._name, hass_id)
        LOGGER.debug("Completed task with id %s in account %s", hass_id, self._name)

    async def _complete_task(self, rtm_id: tuple[str, str, str]) -> None:
        """Complete a task."""
        result = await self._client.rtm.timelines.create()
        timeline = result.timeline
        await self._client.rtm.tasks.complete(
            list_id=int(rtm_id[0]),
            taskseries_id=int(rtm_id[1]),
            task_id=int(rtm_id[2]),
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
