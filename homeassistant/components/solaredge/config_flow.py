"""Config flow for the SolarEdge platform."""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError, ClientResponseError
import aiosolaredge
from solaredge_web import SolarEdgeWeb
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from .const import (
    CONF_SECTION_API_AUTH,
    CONF_SECTION_WEB_AUTH,
    CONF_SITE_ID,
    DEFAULT_NAME,
    DOMAIN,
)


class SolarEdgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}

    @callback
    def _async_current_site_ids(self) -> set[str]:
        """Return the site_ids for the domain."""
        return {
            entry.data[CONF_SITE_ID]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_SITE_ID in entry.data
        }

    def _site_in_configuration_exists(self, site_id: str) -> bool:
        """Return True if site_id exists in configuration."""
        return site_id in self._async_current_site_ids()

    async def _async_check_site(self, site_id: str, api_key: str) -> bool:
        """Check if we can connect to the soleredge api service."""
        session = async_get_clientsession(self.hass)
        api = aiosolaredge.SolarEdge(api_key, session)
        try:
            response = await api.get_details(site_id)
            if response["details"]["status"].lower() != "active":
                self._errors[CONF_SITE_ID] = "site_not_active"
                return False
        except (TimeoutError, ClientError, socket.gaierror):
            self._errors[CONF_SITE_ID] = "cannot_connect"
            return False
        except KeyError:
            self._errors[CONF_SITE_ID] = "invalid_api_key"
            return False
        return True

    async def _async_check_web_login(
        self, site_id: str, username: str, password: str
    ) -> bool:
        """Validate the user input allows us to connect to the web service."""
        api = SolarEdgeWeb(
            username=username,
            password=password,
            site_id=site_id,
            session=async_get_clientsession(self.hass),
        )
        try:
            await api.async_get_equipment()
        except ClientResponseError as err:
            if err.status in (401, 403):
                self._errors["base"] = "invalid_auth"
            else:
                self._errors["base"] = "cannot_connect"
            return False
        except (TimeoutError, ClientError):
            self._errors["base"] = "cannot_connect"
            return False
        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes an integration or reconfigures it."""
        self._errors = {}
        entry = None
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()

        if user_input is not None:
            name = slugify(user_input.get(CONF_NAME, DEFAULT_NAME))
            if self.source == SOURCE_RECONFIGURE:
                if TYPE_CHECKING:
                    assert entry
                site_id = entry.data[CONF_SITE_ID]
            else:
                site_id = user_input[CONF_SITE_ID]
            api_auth = user_input.get(CONF_SECTION_API_AUTH, {})
            web_auth = user_input.get(CONF_SECTION_WEB_AUTH, {})
            api_key = api_auth.get(CONF_API_KEY)
            username = web_auth.get(CONF_USERNAME)

            if self.source != SOURCE_RECONFIGURE and self._site_in_configuration_exists(
                site_id
            ):
                self._errors[CONF_SITE_ID] = "already_configured"
            elif not api_key and not username:
                self._errors["base"] = "auth_missing"
            else:
                api_key_ok = True
                if api_key:
                    api_key_ok = await self._async_check_site(site_id, api_key)

                web_login_ok = True
                if api_key_ok and username:
                    web_login_ok = await self._async_check_web_login(
                        site_id, username, web_auth[CONF_PASSWORD]
                    )

                if api_key_ok and web_login_ok:
                    data = {CONF_SITE_ID: site_id}
                    if api_key:
                        data[CONF_API_KEY] = api_key
                    if username:
                        data[CONF_USERNAME] = username
                        data[CONF_PASSWORD] = web_auth[CONF_PASSWORD]

                    if self.source == SOURCE_RECONFIGURE:
                        if TYPE_CHECKING:
                            assert entry
                        return self.async_update_reload_and_abort(entry, data=data)

                    return self.async_create_entry(title=name, data=data)
        elif self.source == SOURCE_RECONFIGURE:
            if TYPE_CHECKING:
                assert entry
            user_input = {
                CONF_SECTION_API_AUTH: {CONF_API_KEY: entry.data.get(CONF_API_KEY, "")},
                CONF_SECTION_WEB_AUTH: {
                    CONF_USERNAME: entry.data.get(CONF_USERNAME, ""),
                    CONF_PASSWORD: entry.data.get(CONF_PASSWORD, ""),
                },
            }
        else:
            user_input = {}

        data_schema_dict: dict[vol.Marker, Any] = {}
        if self.source != SOURCE_RECONFIGURE:
            data_schema_dict[
                vol.Required(CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME))
            ] = str
            data_schema_dict[
                vol.Required(CONF_SITE_ID, default=user_input.get(CONF_SITE_ID, ""))
            ] = str

        data_schema_dict.update(
            {
                vol.Optional(CONF_SECTION_API_AUTH): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                CONF_API_KEY,
                                default=user_input.get(CONF_SECTION_API_AUTH, {}).get(
                                    CONF_API_KEY, ""
                                ),
                            ): str,
                        }
                    ),
                    options={"collapsed": False},
                ),
                vol.Optional(CONF_SECTION_WEB_AUTH): section(
                    vol.Schema(
                        {
                            vol.Inclusive(
                                CONF_USERNAME,
                                "web_account",
                                default=user_input.get(CONF_SECTION_WEB_AUTH, {}).get(
                                    CONF_USERNAME, ""
                                ),
                            ): str,
                            vol.Inclusive(
                                CONF_PASSWORD,
                                "web_account",
                                default=user_input.get(CONF_SECTION_WEB_AUTH, {}).get(
                                    CONF_PASSWORD, ""
                                ),
                            ): str,
                        }
                    ),
                    options={"collapsed": False},
                ),
            }
        )
        data_schema = vol.Schema(data_schema_dict)

        step_id = "user"
        description_placeholders = {}
        if self.source == SOURCE_RECONFIGURE:
            if TYPE_CHECKING:
                assert entry
            step_id = "reconfigure"
            description_placeholders["site_id"] = entry.data[CONF_SITE_ID]

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=self._errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initiated by the user."""
        return await self.async_step_user(user_input)
