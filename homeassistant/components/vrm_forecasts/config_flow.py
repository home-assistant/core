"""Config flow for the Victron VRM Solar Forecast integration."""

from __future__ import annotations

import logging
from typing import Any

from victron_vrm import VictronVRMClient
from victron_vrm.exceptions import AuthenticationError, VictronVRMError
from victron_vrm.models import Site
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_API_KEY, CONF_SITE_ID, DOMAIN
from .coordinator import is_jwt
from .errors import CannotConnect, InvalidAuth, SiteNotFound

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class VRMClientHolder:
    """Holds the VRM client."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        """Initialize the VRM client holder."""
        self.client = VictronVRMClient(
            token=api_key,
            token_type="Bearer" if is_jwt(api_key) else "Token",
            client_session=get_async_client(hass),
        )

    async def get_site(self, site_id: int) -> Site | None:
        """Get the site data."""
        return await self.client.users.get_site(site_id)

    async def list_sites(self) -> list[Site]:
        """List all sites available to the authenticated user."""
        return await self.client.users.list_sites()


class VRMForecastsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Victron VRM Solar Forecast."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._api_key: str | None = None
        self._sites: list[Site] = []

    def _build_site_options(self) -> list[SelectOptionDict]:
        """Build selector options for the available sites."""
        return [
            SelectOptionDict(
                value=str(site.id), label=f"{(site.name or 'Site')} (ID:{site.id})"
            )
            for site in self._sites
        ]

    async def _async_validate_token_and_fetch_sites(self, api_key: str) -> list[Site]:
        """Validate the API token and return available sites.

        Raises InvalidAuth on bad/unauthorized token; CannotConnect on other errors.
        """
        client = VRMClientHolder(self.hass, api_key)
        try:
            sites = await client.list_sites()
        except AuthenticationError as err:
            raise InvalidAuth("Invalid authentication or permission") from err
        except VictronVRMError as err:
            if getattr(err, "status_code", None) in (401, 403):
                raise InvalidAuth("Invalid authentication or permission") from err
            raise CannotConnect(f"Cannot connect to VRM API: {err}") from err
        else:
            return sites

    async def _async_validate_selected_site(self, api_key: str, site_id: int) -> Site:
        """Validate access to the selected site and return its data."""
        client = VRMClientHolder(self.hass, api_key)
        try:
            site_data = await client.get_site(site_id)
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
            api_key: str = user_input[CONF_API_KEY]
            try:
                sites = await self._async_validate_token_and_fetch_sites(api_key)
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
                self._api_key = api_key
                # Sort sites by name then id for stable order
                self._sites = sorted(sites, key=lambda s: (s.name or "", s.id))
                return await self.async_step_select_site()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_select_site(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Second step: present sites and validate selection."""
        assert self._api_key is not None

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
            site = await self._async_validate_selected_site(self._api_key, site_id)
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
                title=f"VRM Forecast for {site.name}",
                data={CONF_API_KEY: self._api_key, CONF_SITE_ID: site_id},
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
