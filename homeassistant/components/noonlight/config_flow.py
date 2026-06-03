"""Config flow for the Noonlight integration."""

import logging
from typing import Any

from noonlight_dispatch import (
    NoonlightAuthError,
    NoonlightClient,
    NoonlightConnectionError,
    NoonlightError,
    NoonlightResponseError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_ENVIRONMENT,
    DEFAULT_ENVIRONMENT,
    DOMAIN,
    ENV_CUSTOM,
    ENVIRONMENTS,
    resolve_base_url,
)

_LOGGER = logging.getLogger(__name__)


class _CannotConnect(Exception):
    """Credentials step could not reach Noonlight."""


class _InvalidAuth(Exception):
    """Noonlight rejected the supplied token."""


async def _validate_credentials(
    hass: HomeAssistant, environment: str, base_url: str | None, token: str
) -> None:
    """Probe Noonlight to confirm token + reachability without dispatching.

    A GET against a bogus alarm id has no side effects: a 401 means the token
    is bad, a 404 means we are reachable and authorised, and a 5xx outage or
    429 rate-limit means Noonlight is not answering normally (treated as a
    connection problem so we do not create an entry against a broken backend).
    """
    api = NoonlightClient(
        get_async_client(hass),
        token,
        base_url=resolve_base_url(environment, base_url),
    )
    try:
        await api.get_alarm_status("connection-test")
    except NoonlightAuthError as err:
        raise _InvalidAuth from err
    except NoonlightConnectionError as err:
        raise _CannotConnect from err
    except NoonlightResponseError as err:
        # Only a 404 on the bogus id proves reachable + authorised; any other
        # status (5xx outage, 429 rate-limit) must not be accepted as valid.
        if err.status_code != 404:
            raise _CannotConnect from err
    except NoonlightError as err:
        # Other reachable-but-unusual response — reachable + authorised.
        _LOGGER.debug("Noonlight validation probe returned: %s", err)


def _environment_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=list(ENVIRONMENTS),
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="environment",
        )
    )


class NoonlightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Noonlight UI setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the API token and environment, then validate them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            environment = user_input[CONF_ENVIRONMENT]
            base_url = user_input.get(CONF_BASE_URL) or None
            if environment == ENV_CUSTOM and not base_url:
                errors[CONF_BASE_URL] = "base_url_required"
            else:
                # One entry per Noonlight endpoint (prod/sandbox/each custom URL).
                await self.async_set_unique_id(resolve_base_url(environment, base_url))
                self._abort_if_unique_id_configured()
                try:
                    await _validate_credentials(
                        self.hass, environment, base_url, user_input[CONF_API_TOKEN]
                    )
                except _InvalidAuth:
                    errors["base"] = "invalid_auth"
                except _CannotConnect:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=f"Noonlight {environment.capitalize()}",
                        data={
                            CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                            CONF_ENVIRONMENT: environment,
                            CONF_BASE_URL: base_url,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_API_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_ENVIRONMENT, default=DEFAULT_ENVIRONMENT
                ): _environment_selector(),
                vol.Optional(CONF_BASE_URL): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
