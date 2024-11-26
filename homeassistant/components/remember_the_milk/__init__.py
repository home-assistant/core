"""Support to interact with Remember The Milk."""

import json
import logging
from pathlib import Path

from rtmapi import Rtm
import voluptuous as vol

from homeassistant.components import configurator
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .entity import RememberTheMilkEntity

# httplib2 is a transitive dependency from RtmAPI. If this dependency is not
# set explicitly, the library does not work.
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
    """Set up the Remember the milk component."""
    component = EntityComponent[RememberTheMilkEntity](_LOGGER, DOMAIN, hass)

    stored_rtm_config = RememberTheMilkConfiguration(hass)
    for rtm_config in config[DOMAIN]:
        account_name = rtm_config[CONF_NAME]
        _LOGGER.debug("Adding Remember the milk account %s", account_name)
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
    entity = RememberTheMilkEntity(
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
    request_id = None
    api = Rtm(api_key, shared_secret, "write", None)
    url, frob = api.authenticate_desktop()
    _LOGGER.debug("Sent authentication request to server")

    def register_account_callback(fields: list[dict[str, str]]) -> None:
        """Call for register the configurator."""
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

    This class stores the authentication token it get from the backend.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Create new instance of configuration."""
        self._config_file_path = hass.config.path(CONFIG_FILE_NAME)
        self._config = {}
        _LOGGER.debug("Loading configuration from file: %s", self._config_file_path)
        try:
            self._config = json.loads(
                Path(self._config_file_path).read_text(encoding="utf8")
            )
        except FileNotFoundError:
            _LOGGER.debug("Missing configuration file: %s", self._config_file_path)
        except OSError:
            _LOGGER.debug(
                "Failed to read from configuration file, %s, using empty configuration",
                self._config_file_path,
            )
        except ValueError:
            _LOGGER.error(
                "Failed to parse configuration file, %s, using empty configuration",
                self._config_file_path,
            )

    def _save_config(self) -> None:
        """Write the configuration to a file."""
        Path(self._config_file_path).write_text(
            json.dumps(self._config), encoding="utf8"
        )

    def get_token(self, profile_name: str) -> str | None:
        """Get the server token for a profile."""
        if profile_name in self._config:
            return self._config[profile_name][CONF_TOKEN]
        return None

    def set_token(self, profile_name: str, token: str) -> None:
        """Store a new server token for a profile."""
        self._initialize_profile(profile_name)
        self._config[profile_name][CONF_TOKEN] = token
        self._save_config()

    def delete_token(self, profile_name: str) -> None:
        """Delete a token for a profile.

        Usually called when the token has expired.
        """
        self._config.pop(profile_name, None)
        self._save_config()

    def _initialize_profile(self, profile_name: str) -> None:
        """Initialize the data structures for a profile."""
        if profile_name not in self._config:
            self._config[profile_name] = {}
        if CONF_ID_MAP not in self._config[profile_name]:
            self._config[profile_name][CONF_ID_MAP] = {}

    def get_rtm_id(
        self, profile_name: str, hass_id: str
    ) -> tuple[str, str, str] | None:
        """Get the RTM ids for a Home Assistant task ID.

        The id of a RTM tasks consists of the tuple:
        list id, timeseries id and the task id.
        """
        self._initialize_profile(profile_name)
        ids = self._config[profile_name][CONF_ID_MAP].get(hass_id)
        if ids is None:
            return None
        return ids[CONF_LIST_ID], ids[CONF_TIMESERIES_ID], ids[CONF_TASK_ID]

    def set_rtm_id(
        self,
        profile_name: str,
        hass_id: str,
        list_id: str,
        time_series_id: str,
        rtm_task_id: str,
    ) -> None:
        """Add/Update the RTM task ID for a Home Assistant task IS."""
        self._initialize_profile(profile_name)
        id_tuple = {
            CONF_LIST_ID: list_id,
            CONF_TIMESERIES_ID: time_series_id,
            CONF_TASK_ID: rtm_task_id,
        }
        self._config[profile_name][CONF_ID_MAP][hass_id] = id_tuple
        self._save_config()

    def delete_rtm_id(self, profile_name: str, hass_id: str) -> None:
        """Delete a key mapping."""
        self._initialize_profile(profile_name)
        if hass_id in self._config[profile_name][CONF_ID_MAP]:
            del self._config[profile_name][CONF_ID_MAP][hass_id]
            self._save_config()
