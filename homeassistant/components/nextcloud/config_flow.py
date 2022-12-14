"""Config flow for Nextcloud integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from nextcloudmonitor import NextcloudMonitor, NextcloudMonitorError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("url"): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional("scan_interval", default=timedelta(seconds=60)): timedelta,
        vol.Optional("verify_ssl", default=True): bool,
    }
)


class NextCloud:
    """Nextcloud class handler."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        username: str,
        password: str,
        verify_ssl: bool,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.url = url
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.ncm = None

    def setup(self):
        """Call setup functions first to create connection with nextcloud server.

        Raises:
            NextcloudMonitorError: Connection was not established
        """
        self.ncm = NextcloudMonitor(
            self.url, self.username, self.password, self.verify_ssl
        )
        self.__set_data_points_to_hass()

    def update(self):
        """Update download actual nextcloud data.

        Raises:
            UninitializedObject: Setup function was not called, or it failed
        """
        if self.ncm is None:
            raise UninitializedObject()

        self.ncm.update()
        self.__set_data_points_to_hass()

    def __set_data_points_to_hass(self):
        self.hass.data[DOMAIN] = self.__get_ncm_data_points()
        self.hass.data[DOMAIN]["instance"] = self.url

    def __get_ncm_data_points(self, key_path="", leaf=False):
        if self.ncm is None:
            raise UninitializedObject()

        return self.__get_data_points(self.ncm.data, key_path, leaf)

    # Use recursion to create list of sensors & values based on nextcloud api data
    def __get_data_points(self, api_data, key_path="", leaf=False):
        """Use Recursion to discover data-points and values.

        Get dictionary of data-points by recursing through dict returned by api until
        the dictionary value does not contain another dictionary and use the
        resulting path of dictionary keys and resulting value as the name/value
        for the data-point.

        returns: dictionary of data-point/values
        """
        result = {}
        for key, value in api_data.items():
            if isinstance(value, dict):
                if leaf:
                    key_path = f"{key}_"
                if not leaf:
                    key_path += f"{key}_"
                leaf = True
                result.update(self.__get_data_points(value, key_path, leaf))
            else:
                result[f"{DOMAIN}_{key_path}{key}"] = value
                leaf = False
        return result


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    next_cloud_var = NextCloud(
        hass, data["url"], data["username"], data["password"], data["verify_ssl"]
    )

    await hass.async_add_executor_job(next_cloud_var.setup)

    def update(datetime):
        """Update data from nextcloud api."""
        try:
            next_cloud_var.update()
        except UninitializedObject:
            return False

    track_time_interval(hass, update, data["scan_interval"])

    # Return info that you want to store in the config entry.
    return {"title": "Nextcloud"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nextcloud."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except NextcloudMonitorError:
            errors["base"] = "cannot_connect"
        except UninitializedObject:
            errors["base"] = "uninitialized"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class UninitializedObject(HomeAssistantError):
    """Error to indicate we didn't initialize object."""
