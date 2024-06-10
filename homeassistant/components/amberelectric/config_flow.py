"""Config flow for the Amber Electric integration."""

from __future__ import annotations

import amberelectric
from amberelectric.api import amber_api
from amberelectric.model.site import Site, SiteStatus
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_SITE_ID, CONF_SITE_NAME, DOMAIN

API_URL = "https://app.amber.com.au/developers"


def generate_site_selector_name(site: Site) -> str:
    """Generate the name to show in the site drop down in the configuration flow."""
    if site.status == SiteStatus.CLOSED:
        return site.nmi + " (Closed: " + site.closed_on.isoformat() + ")"  # type: ignore[no-any-return]
    if site.status == SiteStatus.PENDING:
        return site.nmi + " (Pending)"  # type: ignore[no-any-return]
    return site.nmi  # type: ignore[no-any-return]


def filter_sites(sites: list[Site]) -> list[Site]:
    """Deduplicates the list of sites."""
    filtered: list[Site] = []
    filtered_nmi: set[str] = set()

    for site in sorted(sites, key=lambda site: site.status.value):
        if site.status == SiteStatus.ACTIVE or site.nmi not in filtered_nmi:
            filtered.append(site)
            filtered_nmi.add(site.nmi)

    return filtered


class AmberElectricConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}
        self._sites: list[Site] | None = None
        self._api_token: str | None = None

    def _fetch_sites(self, token: str) -> list[Site] | None:
        configuration = amberelectric.Configuration(access_token=token)
        api: amber_api.AmberApi = amber_api.AmberApi.create(configuration)

        try:
            sites: list[Site] = filter_sites(api.get_sites())
        except amberelectric.ApiException as api_exception:
            if api_exception.status == 403:
                self._errors[CONF_API_TOKEN] = "invalid_api_token"
            else:
                self._errors[CONF_API_TOKEN] = "unknown_error"
            return None

        if len(sites) == 0:
            self._errors[CONF_API_TOKEN] = "no_site"
            return None
        return sites

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Step to select site."""
        self._errors = {}

        assert self._sites is not None
        assert self._api_token is not None

        if user_input is not None:
            site_id = user_input[CONF_SITE_ID]
            name = user_input.get(CONF_SITE_NAME, site_id)
            return self.async_create_entry(
                title=name,
                data={CONF_SITE_ID: site_id, CONF_API_TOKEN: self._api_token},
            )

        return self.async_show_form(
            step_id="site",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SITE_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=site.id,
                                    label=generate_site_selector_name(site),
                                )
                                for site in self._sites
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_SITE_NAME): str,
                }
            ),
            errors=self._errors,
        )
