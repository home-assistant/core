"""Config flow for ROMY integration."""
from __future__ import annotations

import json
import logging

import voluptuous as vol

from homeassistant import config_entries

from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .utils import async_query, async_query_with_http_status

_LOGGER = logging.getLogger(__name__)


def _schema_with_defaults(
    host: str = "", port: int = 8080, name: str = ""
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): cv.string,
            vol.Required(CONF_PORT, default=port): cv.port,
            vol.Required(CONF_NAME, default=name): cv.string,
        },
    )


def _schema_with_defaults_and_password(
    host: str = "", port: int = 8080, name: str = "", password: str = ""
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): cv.string,
            vol.Required(CONF_PORT, default=port): cv.port,
            vol.Required(CONF_NAME, default=name): cv.string,
            vol.Required(CONF_PASSWORD, default=password): vol.All(str, vol.Length(8)),
        },
    )


class RomyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for ROMY."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Handle a config flow for ROMY."""
        self.discovery_schema = None
        self.local_http_interface_is_locked = False
        self.host: str | None = None
        self.port: int | None = None
        self.name: str | None = None
        self.password: str | None = None

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors = {}
        data = self.discovery_schema or _schema_with_defaults()

        if user_input is not None:
            # Validate the user input
            if "host" not in user_input:
                errors["host"] = "Please enter a host."
            if "port" not in user_input:
                errors["port"] = "Please enter a port."
            if "name" not in user_input:
                errors["name"] = "Please enter a name."

            if not errors:
                ## Save the user input and finish the setup
                self.host = user_input["host"]
                self.port = int(user_input["port"])
                self.name = user_input["name"]

                # send unlock code
                if self.local_http_interface_is_locked:
                    self.password = user_input["password"]
                    ret, response = await async_query(
                        self.hass,
                        self.host,
                        int(self.port),
                        f"set/unlock_http?pass={self.password}",
                    )
                    if not ret:
                        _LOGGER.error("Unlock of ROMY robot failed: %s", response)
                        errors[CONF_PASSWORD] = "wrong password"
                        return self.async_show_form(
                            step_id="user", data_schema=data, errors=errors
                        )

                # set name of robot
                ret, _ = await async_query(
                    self.hass,
                    self.host,
                    int(self.port),
                    f"set/robot_name?name={self.name}",
                )
                if not ret:
                    _LOGGER.error("Failed to set robot name to: %s", self.name)

                return self.async_create_entry(
                    title=user_input["name"], data=user_input
                )

        return self.async_show_form(step_id="user", data_schema=data, errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""

        _LOGGER.debug("Zeroconf discovery_info: %s", discovery_info)

        # extract unique id and stop discovery if robot is already added
        unique_id = discovery_info.hostname.split(".")[0]
        _LOGGER.debug("Unique_id: %s", unique_id)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # set to default port
        discovery_info.port = 8080

        # get robot name
        ret, json_response = await async_query(
            self.hass, discovery_info.host, discovery_info.port, "get/robot_name"
        )

        # in case it did not work try again on different port
        if not ret:
            discovery_info.port = 10009
            ret, json_response = await async_query(
                self.hass, discovery_info.host, discovery_info.port, "get/robot_name"
            )
            if not ret:
                _LOGGER.error("Error connecting to ROMY robot!")
                return self.async_abort(reason="unable_to_connect")

        status = json.loads(json_response)
        discovery_info.name = status["name"]

        # check if local http interface is locked
        _, _, http_status = await async_query_with_http_status(
            self.hass,
            discovery_info.host,
            discovery_info.port,
            "ishttpinterfacelocked",
        )
        if http_status == 400:
            self.local_http_interface_is_locked = False
        if http_status == 403:
            self.local_http_interface_is_locked = True
            _LOGGER.info("ROMYs local http interface is locked!")

        self.context.update(
            {
                "title_placeholders": {
                    "name": f"{discovery_info.name} ({discovery_info.host})"
                },
                "configuration_url": f"http://{discovery_info.host}:{discovery_info.port}",
            }
        )

        # if interface is locked add password to scheme
        if self.local_http_interface_is_locked:
            self.discovery_schema = _schema_with_defaults_and_password(
                host=discovery_info.host,
                port=discovery_info.port,
                name=discovery_info.name,
                password="",
            )
        else:
            self.discovery_schema = _schema_with_defaults(
                host=discovery_info.host,
                port=discovery_info.port,
                name=discovery_info.name,
            )

        return await self.async_step_user()
