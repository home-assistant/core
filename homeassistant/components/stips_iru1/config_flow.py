"""Config flow for STIPS IRU1."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    StipsApiAuthError,
    StipsApiClient,
    StipsApiError,
    StipsApiPermissionError,
)
from .catalog import async_fetch_catalog_devices
from .const import (
    CONF_API_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_API_HOST,
    DOMAIN,
)


class StipsIru1ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle STIPS IRU1 config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single-step setup: login and download full account IR catalog."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_host = user_input[CONF_API_HOST]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            session = async_get_clientsession(self.hass)
            client = StipsApiClient(host=api_host, session=session)
            try:
                await client.login(username, password)
                areas = await client.get_areas()
            except StipsApiAuthError:
                errors["base"] = "invalid_auth"
            except StipsApiPermissionError:
                errors["base"] = "no_catalog_permission"
            except StipsApiError:
                errors["base"] = "cannot_connect"
            except (TypeError, ValueError):
                errors["base"] = "unknown"
            else:
                if not areas:
                    errors["base"] = "no_areas"
                else:
                    try:
                        _, catalog_devices = await async_fetch_catalog_devices(client, areas)
                    except StipsApiError:
                        errors["base"] = "cannot_connect"
                    else:
                        if not catalog_devices:
                            errors["base"] = "no_devices"
                        else:
                            normalized_host = str(api_host).strip().lower()
                            normalized_username = str(username).strip().lower()
                            await self.async_set_unique_id(
                                f"{DOMAIN}_{normalized_host}_{normalized_username}"
                            )
                            self._abort_if_unique_id_configured()
                            return self.async_create_entry(
                                title=f"STIPS ({username})",
                                data={
                                    CONF_API_HOST: api_host,
                                    CONF_USERNAME: username,
                                    "areas": areas,
                                    "devices": catalog_devices,
                                },
                            )

        schema = vol.Schema(
            {
                vol.Required(CONF_API_HOST, default=DEFAULT_API_HOST): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

