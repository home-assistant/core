"""Config flow for the TrueNAS integration."""

import logging
from typing import Any, override

from aiotruenas import (
    TrueNASAuthenticationError,
    TrueNASCallError,
    TrueNASClient,
    TrueNASError,
    TrueNASSystem,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, ERRNAME_PERMISSION_DENIED

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        probatio.Required(CONF_VERIFY_SSL, default=False): bool,
    }
)


class TrueNASConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TrueNAS."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                client = TrueNASClient(
                    user_input[CONF_HOST],
                    user_input[CONF_API_KEY],
                    verify_ssl=user_input[CONF_VERIFY_SSL],
                )
            except ValueError:
                # The host contains a scheme or a path.
                errors[CONF_HOST] = "invalid_host"
            else:
                try:
                    await client.connect()
                    system = TrueNASSystem(client)
                    system_id = await system.get_system_id()
                    info = await system.get_system_info()
                except TrueNASAuthenticationError:
                    errors["base"] = "invalid_auth"
                except TrueNASCallError as err:
                    errors["base"] = (
                        "permission_denied"
                        if err.errname == ERRNAME_PERMISSION_DENIED
                        else "cannot_connect"
                    )
                except TrueNASError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(system_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=info.hostname or user_input[CONF_HOST],
                        data=user_input,
                    )
                finally:
                    await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
