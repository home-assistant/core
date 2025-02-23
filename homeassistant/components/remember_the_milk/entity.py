"""Support to interact with Remember The Milk."""

from rtmapi import Rtm, RtmRequestFailedException

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
        self._check_token()
        LOGGER.debug("Instance created for account %s", self._name)

    def _check_token(self) -> bool:
        """Check if the API token is still valid.

        If it is not valid any more, delete it from the configuration. This
        will trigger a new authentication process.
        """
        valid = self._rtm_api.token_valid()
        if not valid:
            LOGGER.error(
                "Token for account %s is invalid. You need to register again!",
                self.name,
            )
            self._rtm_config.delete_token(self._name)
            self._token_valid = False
        else:
            self._token_valid = True
        return self._token_valid

    def create_task(self, call: ServiceCall) -> None:
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
            result = self._rtm_api.rtm.timelines.create()
            timeline = result.timeline.value

            if rtm_id is None:
                result = self._rtm_api.rtm.tasks.add(
                    timeline=timeline, name=task_name, parse="1"
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
                self._rtm_api.rtm.tasks.setName(
                    name=task_name,
                    list_id=rtm_id[0],
                    taskseries_id=rtm_id[1],
                    task_id=rtm_id[2],
                    timeline=timeline,
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

    def complete_task(self, call: ServiceCall) -> None:
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
            result = self._rtm_api.rtm.timelines.create()
            timeline = result.timeline.value
            self._rtm_api.rtm.tasks.complete(
                list_id=rtm_id[0],
                taskseries_id=rtm_id[1],
                task_id=rtm_id[2],
                timeline=timeline,
            )
            self._rtm_config.delete_rtm_id(self._name, hass_id)
            LOGGER.debug("Completed task with id %s in account %s", hass_id, self._name)
        except RtmRequestFailedException as rtm_exception:
            LOGGER.error(
                "Error creating new Remember The Milk task for account %s: %s",
                self._name,
                rtm_exception,
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
