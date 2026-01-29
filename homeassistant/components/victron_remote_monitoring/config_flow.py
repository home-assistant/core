"""Config flow for the Victron VRM Solar Forecast integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from victron_vrm import VictronVRMClient
from victron_vrm.exceptions import AuthenticationError, VictronVRMError
from victron_vrm.models import Site
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_API_TOKEN, CONF_SITE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): str})


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class SiteNotFound(HomeAssistantError):
    """Error to indicate the site was not found."""


class VictronRemoteMonitoringFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Victron Remote Monitoring.

    Supports reauthentication when the stored token becomes invalid.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._api_token: str | None = None
        self._sites: list[Site] = []

    def _build_site_options(self) -> list[SelectOptionDict]:
        """Build selector options for the available sites."""
        return [
            SelectOptionDict(
                value=str(site.id), label=f"{(site.name or 'Site')} (ID:{site.id})"
            )
            for site in self._sites
        ]

    async def _async_validate_token_and_fetch_sites(self, api_token: str) -> list[Site]:
        """Validate the API token and return available sites.

        Raises InvalidAuth on bad/unauthorized token; CannotConnect on other errors.
        """
        client = VictronVRMClient(
            token=api_token,
            client_session=async_get_clientsession(self.hass),
        )
        try:
            sites = await client.users.list_sites()
        except AuthenticationError as err:
            raise InvalidAuth("Invalid authentication or permission") from err
        except VictronVRMError as err:
            if getattr(err, "status_code", None) in (401, 403):
                raise InvalidAuth("Invalid authentication or permission") from err
            raise CannotConnect(f"Cannot connect to VRM API: {err}") from err
        else:
            return sites

    async def _async_validate_selected_site(self, api_token: str, site_id: int) -> Site:
        """Validate access to the selected site and return its data."""
        client = VictronVRMClient(
            token=api_token,
            client_session=async_get_clientsession(self.hass),
        )
        try:
            site_data = await client.users.get_site(site_id)
        except AuthenticationError as err:
            raise InvalidAuth("Invalid authentication or permission") from err
        except VictronVRMError as err:
            if getattr(err, "status_code", None) in (401, 403):
                raise InvalidAuth("Invalid authentication or permission") from err
            raise CannotConnect(f"Cannot connect to VRM API: {err}") from err
        if site_data is None:
            raise SiteNotFound(f"Site with ID {site_id} not found")
        return site_data

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step: ask for API token and validate it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_token: str = user_input[CONF_API_TOKEN]
            try:
                sites = await self._async_validate_token_and_fetch_sites(api_token)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not sites:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=STEP_USER_DATA_SCHEMA,
                        errors={"base": "no_sites"},
                    )
                self._api_token = api_token
                # Sort sites by name then id for stable order
                self._sites = sorted(sites, key=lambda s: (s.name or "", s.id))
                if len(self._sites) == 1:
                    # Only one site available, skip site selection step
                    site = self._sites[0]
                    await self.async_set_unique_id(
                        str(site.id), raise_on_progress=False
                    )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"VRM for {site.name}",
                        data={CONF_API_TOKEN: self._api_token, CONF_SITE_ID: site.id},
                    )
                return await self.async_step_select_site()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_select_site(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Second step: present sites and validate selection."""
        assert self._api_token is not None

        if user_input is None:
            site_options = self._build_site_options()
            return self.async_show_form(
                step_id="select_site",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_SITE_ID): SelectSelector(
                            SelectSelectorConfig(
                                options=site_options, mode=SelectSelectorMode.DROPDOWN
                            )
                        )
                    }
                ),
            )

        # User submitted a site selection
        site_id = int(user_input[CONF_SITE_ID])
        # Prevent duplicate entries for the same site
        self._async_abort_entries_match({CONF_SITE_ID: site_id})

        errors: dict[str, str] = {}
        try:
            site = await self._async_validate_selected_site(self._api_token, site_id)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except SiteNotFound:
            errors["base"] = "site_not_found"
        except Exception:  # pragma: no cover - unexpected
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Ensure unique ID per site to avoid duplicates across reloads
            await self.async_set_unique_id(str(site_id), raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"VRM for {site.name}",
                data={CONF_API_TOKEN: self._api_token, CONF_SITE_ID: site_id},
            )

        # If we reach here, show the selection form again with errors
        site_options = self._build_site_options()
        return self.async_show_form(
            step_id="select_site",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SITE_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=site_options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication by asking for a (new) API token.

        We only need the token again; the site is fixed per entry and set as unique id.
        """
        self._api_token = None
        self._sites = []
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation with new token."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            new_token = user_input[CONF_API_TOKEN]
            site_id: int = reauth_entry.data[CONF_SITE_ID]
            try:
                # Validate the token by fetching the site for the existing entry
                await self._async_validate_selected_site(new_token, site_id)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except SiteNotFound:
                # Site removed or no longer visible to the account; treat as cannot connect
                errors["base"] = "site_not_found"
            except Exception:  # pragma: no cover - unexpected
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                # Update stored token and reload entry
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_TOKEN: new_token},
                    reason="reauth_successful",
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )
