"""Config flow for Rexense gateways."""

import logging
from typing import Any, override

from aiorexense import (
    DEFAULT_GATEWAY_PORT,
    RexenseAuthenticationError,
    RexenseClient,
    RexenseError,
    UnsupportedTaxonomyError,
    gateway_identity,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Optional(CONF_PORT, default=DEFAULT_GATEWAY_PORT): probatio.Port(),
        probatio.Optional(CONF_API_KEY, default=""): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        probatio.Optional(CONF_SSL, default=False): bool,
        probatio.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


class RexenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Connect to one physical Rexense gateway."""

    VERSION = 1

    async def _async_validate_input(self, data: dict[str, Any]) -> dict[str, Any]:
        """Check the connection and release the temporary socket."""
        client = RexenseClient(
            async_get_clientsession(self.hass),
            data[CONF_HOST],
            data[CONF_PORT],
            data[CONF_API_KEY],
            use_ssl=data[CONF_SSL],
            verify_ssl=data[CONF_VERIFY_SSL],
        )
        try:
            return await client.async_connect()
        finally:
            await client.async_close()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await self._async_validate_input(user_input)
            except RexenseAuthenticationError:
                errors["base"] = "invalid_auth"
            except UnsupportedTaxonomyError:
                errors["base"] = "unsupported_gateway"
            except RexenseError, TimeoutError, ValueError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to Rexense")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(gateway_identity(info))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Rexense {info.get('system', {}).get('model', 'gateway')}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input),
            errors=errors,
        )
