"""SMA Manager Config Flow for UI configuration"""

#  Copyright (c) 2023.
#  All rights reserved to the creator of the following script/program/app, please do not
#  use or distribute without prior authorization from the creator.
#  Creator: Antonio Manuel Nunes Goncalves
#  Email: amng835@gmail.com
#  LinkedIn: https://www.linkedin.com/in/antonio-manuel-goncalves-983926142/
#  Github: https://github.com/DEADSEC-SECURITY

# Built-In Imports
import logging
import re

# Home Assistant Imports
from homeassistant import config_entries

# 3rd-Party Imports
from voluptuous import Schema, Required

# Local Imports
from .const import DOMAIN, CONF_NAME, CONF_HOST, CONF_PORT, CONF_REFRESH_INTERVAL
from .SMA import SMA


_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Enables the Integration to be configured in the UI
    """

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        self._data = {
            CONF_NAME: "SMA Manager",
            CONF_HOST: "239.12.255.254",
            CONF_PORT: 9522,
            CONF_REFRESH_INTERVAL: 10
        }

    def _get_schema(self) -> Schema:
        """
        Generates a schema from data
        """

        return Schema(
            {
                Required(CONF_NAME, default=self._data[CONF_NAME]): str,
                Required(CONF_HOST, default=self._data[CONF_HOST]): str,
                Required(CONF_PORT, default=self._data[CONF_PORT]): int,
                Required(CONF_REFRESH_INTERVAL, default=self._data[CONF_REFRESH_INTERVAL]): int,
            }
        )

    async def async_step_user(self, user_input=None):
        """
        UI form for adding integration

        @param user_input:
        @return:
        """
        errors = {}
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=self._get_schema(), errors=errors
            )

        # Make user inputted data persistent
        self._data[CONF_NAME] = user_input[CONF_NAME]
        self._data[CONF_HOST] = user_input[CONF_HOST]
        self._data[CONF_PORT] = user_input[CONF_PORT]
        self._data[CONF_REFRESH_INTERVAL] = user_input[CONF_REFRESH_INTERVAL]

        # Validate Multicast IP
        if not re.match(r"\A\d{2,3}.\d{2,3}.\d{2,3}.\d{2,3}$", user_input[CONF_HOST]):
            errors["ip"] = "invalid_id"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=self._get_schema(), errors=errors
            )

        # Test the connection
        try:
            sma = SMA(
                user_input[CONF_NAME],
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_REFRESH_INTERVAL],
            )
        except TimeoutError:
            errors["cannot_connect"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=self._get_schema(), errors=errors
            )

        # Check if not integrated already
        await self.async_set_unique_id(sma.serial_number)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
