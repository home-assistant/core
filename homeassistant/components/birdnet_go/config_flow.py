"""Config flow for BirdNET-Go integration."""

from typing import Any, override

from aiobirdnetgo import (
    BirdNetGoAuthenticationError,
    BirdNetGoClient,
    BirdNetGoConnectionError,
    BirdNetGoError,
    BirdNetGoTimeoutError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=65535,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Optional(CONF_SSL, default=False): BooleanSelector(),
    }
)


class BirdNetGoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BirdNET-Go."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_host = user_input[CONF_HOST].strip()
            raw_ssl = bool(user_input.get(CONF_SSL, False))

            session = async_get_clientsession(self.hass)
            try:
                raw_port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
                client = BirdNetGoClient(
                    host=raw_host,
                    port=raw_port,
                    use_ssl=raw_ssl,
                    session=session,
                )
                await client.get_kpis()
            except ValueError:
                errors["base"] = "cannot_connect"
            except BirdNetGoAuthenticationError:
                errors["base"] = "auth_not_supported"
            except BirdNetGoConnectionError, BirdNetGoTimeoutError:
                errors["base"] = "cannot_connect"
            except BirdNetGoError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception during BirdNET-Go setup")
                errors["base"] = "unknown"
            else:
                if not errors:
                    host = client.host
                    port = client.port
                    use_ssl = client.use_ssl
                    user_input[CONF_HOST] = host
                    user_input[CONF_PORT] = port
                    user_input[CONF_SSL] = use_ssl

                    unique_id = f"{host}:{port}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    title = f"{DEFAULT_NAME} ({host}:{port})"
                    return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
