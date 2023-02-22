"""Config flow for the Amber Electric integration."""
from __future__ import annotations

import amberelectric
from amberelectric.api import amber_api
from amberelectric.model.site import Site
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SITE_ID, CONF_SITE_NAME, CONF_SITE_NMI, DOMAIN

API_URL = "https://app.amber.com.au/developers"


class AmberElectricConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}
        self._sites: list[Site] | None = None
        self._api_token: str | None = None

    def _fetch_sites(self, token: str) -> list[Site] | None:
        configuration = amberelectric.Configuration(access_token=token)
        api = amber_api.AmberApi.create(configuration)

        try:
            sites = api.get_sites()
            if len(sites) == 0:
                self._errors[CONF_API_TOKEN] = "no_site"
                return None
            return sites
        except amberelectric.ApiException as api_exception:
            if api_exception.status == 403:
                self._errors[CONF_API_TOKEN] = "invalid_api_token"
            else:
                self._errors[CONF_API_TOKEN] = "unknown_error"
            return None

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Step when user initializes a integration."""
        self._errors = {}
        self._sites = None
        self._api_token = None

        if user_input is not None:
            token = user_input[CONF_API_TOKEN]
            self._sites = await self.hass.async_add_executor_job(
                self._fetch_sites, token
            )

            if self._sites is not None:
                self._api_token = token
                return await self.async_step_site()

        else:
            user_input = {CONF_API_TOKEN: ""}

        return self.async_show_form(
            step_id="user",
            description_placeholders={"api_url": API_URL},
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_TOKEN, default=user_input[CONF_API_TOKEN]
                    ): str,
                }
            ),
            errors=self._errors,
        )

    async def async_step_site(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Step to select site."""
        self._errors = {}

        assert self._sites is not None
        assert self._api_token is not None

        api_token = self._api_token
        if user_input is not None:
            site_nmi = user_input[CONF_SITE_NMI]
            sites = [site for site in self._sites if site.nmi == site_nmi]
            site = sites[0]
            site_id = site.id
            name = user_input.get(CONF_SITE_NAME, site_id)
            return self.async_create_entry(
                title=name,
                data={
                    CONF_SITE_ID: site_id,
                    CONF_API_TOKEN: api_token,
                    CONF_SITE_NMI: site.nmi,
                },
            )

        user_input = {
            CONF_API_TOKEN: api_token,
            CONF_SITE_NMI: "",
            CONF_SITE_NAME: "",
        }

        return self.async_show_form(
            step_id="site",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SITE_NMI, default=user_input[CONF_SITE_NMI]
                    ): vol.In([site.nmi for site in self._sites]),
                    vol.Optional(
                        CONF_SITE_NAME, default=user_input[CONF_SITE_NAME]
                    ): str,
                }
            ),
            errors=self._errors,
        )
