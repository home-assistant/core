"""Support to interact with Remember The Milk."""

import json
import logging
import os

from rtmapi import Rtm, RtmRequestFailedException
import voluptuous as vol

from homeassistant.components import configurator
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME, CONF_TOKEN, STATE_OK
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "remember_the_milk"
DEFAULT_NAME = DOMAIN

CONF_SHARED_SECRET = "shared_secret"
CONF_ID_MAP = "id_map"
CONF_LIST_ID = "list_id"
CONF_TIMESERIES_ID = "timeseries_id"
CONF_TASK_ID = "task_id"

RTM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SHARED_SECRET): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [RTM_SCHEMA])}, extra=vol.ALLOW_EXTRA
)

CONFIG_FILE_NAME = ".remember_the_milk.conf"
SERVICE_CREATE_TASK = "create_task"
SERVICE_COMPLETE_TASK = "complete_task"

SERVICE_SCHEMA_CREATE_TASK = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Optional(CONF_ID): cv.string}
)

SERVICE_SCHEMA_COMPLETE_TASK = vol.Schema({vol.Required(CONF_ID): cv.string})


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Remember the Milk component.

    Args:
        hass (HomeAssistant): Home Assistant instance.
        config (ConfigType): The configuration provided for this component.

    Returns:
        bool: True if setup is successful, False otherwise.
    """
    component = EntityComponent[RememberTheMilk](_LOGGER, DOMAIN, hass)

    stored_rtm_config = RememberTheMilkConfiguration(hass)
    for rtm_config in config[DOMAIN]:
        account_name = rtm_config[CONF_NAME]
        _LOGGER.info("Adding Remember the milk account %s", account_name)
        api_key = rtm_config[CONF_API_KEY]
        shared_secret = rtm_config[CONF_SHARED_SECRET]
        token = stored_rtm_config.get_token(account_name)
        if token:
            _LOGGER.debug("found token for account %s", account_name)
            _create_instance(
                hass,
                account_name,
                api_key,
                shared_secret,
                token,
                stored_rtm_config,
                component,
            )
        else:
            _register_new_account(
                hass, account_name, api_key, shared_secret, stored_rtm_config, component
            )

    _LOGGER.debug("Finished adding all Remember the milk accounts")
    return True


def _create_instance(
    hass, account_name, api_key, shared_secret, token, stored_rtm_config, component
):
    """Create a new Remember The Milk instance.

    Args:
        hass (HomeAssistant): Home Assistant instance.
        account_name (str): The name of the Remember The Milk account.
        api_key (str): The API key for the account.
        shared_secret (str): The shared secret for the account.
        token (str): The authentication token.
        stored_rtm_config (RememberTheMilkConfiguration): Configuration storage instance.
        component (EntityComponent): Entity component for the Remember The Milk integration.
    """
    entity = RememberTheMilk(
        account_name, api_key, shared_secret, token, stored_rtm_config
    )
    component.add_entities([entity])
    hass.services.register(
        DOMAIN,
        f"{account_name}_create_task",
        entity.create_task,
        schema=SERVICE_SCHEMA_CREATE_TASK,
    )
    hass.services.register(
        DOMAIN,
        f"{account_name}_complete_task",
        entity.complete_task,
        schema=SERVICE_SCHEMA_COMPLETE_TASK,
    )


def _register_new_account(
    hass, account_name, api_key, shared_secret, stored_rtm_config, component
):
    """Register a new Remember The Milk account.

    Args:
        hass (HomeAssistant): Home Assistant instance.
        account_name (str): The name of the Remember The Milk account.
        api_key (str): The API key for the account.
        shared_secret (str): The shared secret for the account.
        stored_rtm_config (RememberTheMilkConfiguration): Configuration storage instance.
        component (EntityComponent): Entity component for the Remember The Milk integration.
    """
    request_id = None
    api = Rtm(api_key, shared_secret, "write", None)
    url, frob = api.authenticate_desktop()
    _LOGGER.debug("Sent authentication request to server")

    def register_account_callback(fields: list[dict[str, str]]) -> None:
        """Callback for registering the configurator.

        Args:
            fields (list[dict[str, str]]): Input fields for configuration.
        """
        api.retrieve_token(frob)
        token = api.token
        if api.token is None:
            _LOGGER.error("Failed to register, please try again")
            configurator.notify_errors(
                hass, request_id, "Failed to register, please try again."
            )
            return

        stored_rtm_config.set_token(account_name, token)
        _LOGGER.debug("Retrieved new token from server")

        _create_instance(
            hass,
            account_name,
            api_key,
            shared_secret,
            token,
            stored_rtm_config,
            component,
        )

        configurator.request_done(hass, request_id)

    request_id = configurator.request_config(
        hass,
        f"{DOMAIN} - {account_name}",
        callback=register_account_callback,
        description=(
            "You need to log in to Remember The Milk to"
            "connect your account. \n\n"
            "Step 1: Click on the link 'Remember The Milk login'\n\n"
            "Step 2: Click on 'login completed'"
        ),
        link_name="Remember The Milk login",
        link_url=url,
        submit_caption="login completed",
    )


class RememberTheMilkConfiguration:
    """Internal configuration data for RememberTheMilk class.

    This class stores the authentication token it retrieves from the backend.
    """

    def __init__(self, hass):
        """Initialize a new instance of configuration.

        Args:
            hass (HomeAssistant): Home Assistant instance.
        """
        self._config_file_path = hass.config.path(CONFIG_FILE_NAME)
        if not os.path.isfile(self._config_file_path):
            self._config = {}
            return
        try:
            _LOGGER.debug("Loading configuration from file: %s", self._config_file_path)
            with open(self._config_file_path, encoding="utf8") as config_file:
                self._config = json.load(config_file)
        except ValueError:
            _LOGGER.error(
                "Failed to load configuration file, creating a new one: %s",
                self._config_file_path,
            )
            self._config = {}

    def save_config(self):
        """Write the configuration to a file."""
        with open(self._config_file_path, "w", encoding="utf8") as config_file:
            json.dump(self._config, config_file)

    def get_token(self, profile_name):
        """Get the server token for a profile.

        Args:
            profile_name (str): Name of the profile.

        Returns:
            str or None: The authentication token if available, None otherwise.
        """
        if profile_name in self._config:
            return self._config[profile_name][CONF_TOKEN]
        return None

    def set_token(self, profile_name, token):
        """Store a new server token for a profile.

        Args:
            profile_name (str): Name of the profile.
            token (str): The authentication token.
        """
        self._initialize_profile(profile_name)
        self._config[profile_name][CONF_TOKEN] = token
        self.save_config()

    def delete_token(self, profile_name):
        """Delete a token for a profile.

        Usually called when the token has expired.

        Args:
            profile_name (str): Name of the profile.
        """
        self._config.pop(profile_name, None)
        self.save_config()

    def _initialize_profile(self, profile_name):
        """Initialize the data structures for a profile.

        Args:
            profile_name (str): Name of the profile.
        """
        if profile_name not in self._config:
            self._config[profile_name] = {}
        if CONF_ID_MAP not in self._config[profile_name]:
            self._config[profile_name][CONF_ID_MAP] = {}

    def get_rtm_id(self, profile_name, hass_id):
        """Get the Remember The Milk IDs for a Home Assistant task ID.

        Args:
            profile_name (str): Name of the profile.
            hass_id (str): Home Assistant task ID.

        Returns:
            tuple or None: The RTM IDs (list_id, timeseries_id, task_id) if available, None otherwise.
        """
        self._initialize_profile(profile_name)
        ids = self._config[profile_name][CONF_ID_MAP].get(hass_id)
        if ids is None:
            return None
        return ids[CONF_LIST_ID], ids[CONF_TIMESERIES_ID], ids[CONF_TASK_ID]

    def set_rtm_id(self, profile_name, hass_id, list_id, time_series_id, rtm_task_id):
        """Add/Update the RTM task ID for a Home Assistant task.

        Args:
            profile_name (str): Name of the profile.
            hass_id (str): Home Assistant task ID.
            list_id (str): List ID.
            time_series_id (str): Timeseries ID.
            rtm_task_id (str): Remember The Milk task ID.
        """
        self._initialize_profile(profile_name)
        self._config[profile_name][CONF_ID_MAP][hass_id] = {
            CONF_LIST_ID: list_id,
            CONF_TIMESERIES_ID: time_series_id,
            CONF_TASK_ID: rtm_task_id,
        }
        self.save_config()


def delete_rtm_id(self, profile_name: str, hass_id: str) -> None:
    """Delete a key mapping for a task.

    Args:
        profile_name (str): Name of the Remember The Milk profile.
        hass_id (str): Home Assistant task ID.
    """
    self._initialize_profile(profile_name)
    if hass_id in self._config[profile_name][CONF_ID_MAP]:
        del self._config[profile_name][CONF_ID_MAP][hass_id]
        self.save_config()


class RememberTheMilk(Entity):
    """Representation of an interface to Remember The Milk."""

    def __init__(
        self, name: str, api_key: str, shared_secret: str, token: str, rtm_config: RememberTheMilkConfiguration
    ) -> None:
        """Create a new instance of the Remember The Milk component.

        Args:
            name (str): Name of the Remember The Milk account.
            api_key (str): API key for the account.
            shared_secret (str): Shared secret for the account.
            token (str): Authentication token.
            rtm_config (RememberTheMilkConfiguration): Configuration storage instance.
        """
        self._name = name
        self._api_key = api_key
        self._shared_secret = shared_secret
        self._token = token
        self._rtm_config = rtm_config
        self._rtm_api = Rtm(api_key, shared_secret, "delete", token)
        self._token_valid = None
        self._check_token()
        _LOGGER.debug("Instance created for account %s", self._name)

    def _check_token(self) -> bool:
        """Check if the API token is still valid.

        If the token is no longer valid, delete it from the configuration,
        triggering a new authentication process.

        Returns:
            bool: True if the token is valid, False otherwise.
        """
        valid = self._rtm_api.token_valid()
        if not valid:
            _LOGGER.error(
                "Token for account %s is invalid. You need to register again!", self.name
            )
            self._rtm_config.delete_token(self._name)
            self._token_valid = False
        else:
            self._token_valid = True
        return self._token_valid

    def create_task(self, call: ServiceCall) -> None:
        """Create a new task on Remember The Milk.

        You can use the smart syntax to define the attributes of a new task,
        e.g., "my task #some_tag ^today" will add the tag "some_tag" and set
        the due date to today.

        Args:
            call (ServiceCall): The service call containing task creation data.
        """
        try:
            task_name = call.data[CONF_NAME]
            hass_id = call.data.get(CONF_ID)
            rtm_id = None
            if hass_id is not None:
                rtm_id = self._rtm_config.get_rtm_id(self._name, hass_id)
            result = self._rtm_api.rtm.timelines.create()
            timeline = result.timeline.value

            if hass_id is None or rtm_id is None:
                result = self._rtm_api.rtm.tasks.add(
                    timeline=timeline, name=task_name, parse="1"
                )
                _LOGGER.debug(
                    "Created new task '%s' in account %s", task_name, self.name
                )
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
                _LOGGER.debug(
                    "Updated task with id '%s' in account %s to name %s",
                    hass_id,
                    self.name,
                    task_name,
                )
        except RtmRequestFailedException as rtm_exception:
            _LOGGER.error(
                "Error creating new Remember The Milk task for account %s: %s",
                self._name,
                rtm_exception,
            )

    def complete_task(self, call: ServiceCall) -> None:
        """Complete a task that was previously created by this component.

        Args:
            call (ServiceCall): The service call containing task completion data.
        """
        hass_id = call.data[CONF_ID]
        rtm_id = self._rtm_config.get_rtm_id(self._name, hass_id)
        if rtm_id is None:
            _LOGGER.error(
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
            _LOGGER.debug(
                "Completed task with id %s in account %s", hass_id, self._name
            )
        except RtmRequestFailedException as rtm_exception:
            _LOGGER.error(
                "Error completing Remember The Milk task for account %s: %s",
                self._name,
                rtm_exception,
            )

    @property
    def name(self) -> str:
        """Return the name of the device.

        Returns:
            str: The name of the Remember The Milk account.
        """
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the device.

        Returns:
            str: "API token invalid" if the token is invalid, otherwise returns STATE_OK.
        """
        if not self._token_valid:
            return "API token invalid"
        return STATE_OK
