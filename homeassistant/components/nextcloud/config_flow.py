"""Config flow for Nextcloud integration."""
from __future__ import annotations

import logging
from typing import Any
from datetime import timedelta

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.event import track_time_interval

from .const import DOMAIN
from nextcloudmonitor import NextcloudMonitor, NextcloudMonitorError

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("url"): cv.url,
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional("scan_interval", default=timedelta(seconds=60)): cv.time_period,
        vol.Optional("verify_ssl", default=True): cv.boolean,
    }
)


class NextCloud:
    def __init__(
        self,
        hass: HomeAssistant,
        url: cv.url,
        username: str,
        password: str,
        verify_ssl: cv.boolean,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.url = url
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.ncm = None

    def setup(self):
        self.ncm = NextcloudMonitor(
            self.url, self.username, self.password, self.verify_ssl
        )
        self.setDataPointsToHass()

    def update(self):
        if self.ncm == None:
            raise UninitializedObject()

        self.ncm.update()
        self.setDataPointsToHass()

    def setDataPointsToHass(self):
        self.hass.data[DOMAIN] = self.getDataPoints()
        self.hass.data[DOMAIN]["instance"] = self.url

    def getDataPoints(self, key_path="", leaf=False):
        if self.ncm == None:
            raise UninitializedObject()

        return self.__getDataPoints(self.ncm.data, key_path, leaf)

    # Use recursion to create list of sensors & values based on nextcloud api data
    def __getDataPoints(self, api_data, key_path="", leaf=False):
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
                result.update(self.__getDataPoints(value, key_path, leaf))
            else:
                result[f"{DOMAIN}_{key_path}{key}"] = value
                leaf = False
        return result


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    nextCloudVar = NextCloud(
        hass, data["url"], data["username"], data["password"], data["verify_ssl"]
    )

    await hass.async_add_executor_job(nextCloudVar.setup)

    def update():
        """Update data from nextcloud api."""
        try:
            nextCloudVar.update()
        except:
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
    """Error to indicate we didn't initialize object"""
