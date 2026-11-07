"""Config flow for the TrueNAS integration."""

from collections.abc import Mapping
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
STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


async def _async_validate_input(
    data: Mapping[str, Any],
) -> tuple[dict[str, str], str | None, str | None]:
    """Connect to TrueNAS and return the errors, the system id and the hostname."""
    try:
        client = TrueNASClient(
            data[CONF_HOST], data[CONF_API_KEY], verify_ssl=data[CONF_VERIFY_SSL]
        )
    except ValueError:
        # The host contains a scheme or a path.
        return {CONF_HOST: "invalid_host"}, None, None
    try:
        await client.connect()
        system = TrueNASSystem(client)
        system_id = await system.get_system_id()
        info = await system.get_system_info()
    except TrueNASAuthenticationError:
        error = "invalid_auth"
    except TrueNASCallError as err:
        error = (
            "permission_denied"
            if err.errname == ERRNAME_PERMISSION_DENIED
            else "cannot_connect"
        )
    except TrueNASError:
        error = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        error = "unknown"
    else:
        return {}, system_id, info.hostname
    finally:
        await client.close()
    return {"base": error}, None, None


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
            errors, system_id, hostname = await _async_validate_input(user_input)
            if not errors:
                await self.async_set_unique_id(system_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=hostname or user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle an API key that TrueNAS rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, system_id, _ = await _async_validate_input(
                {**reauth_entry.data, **user_input}
            )
            if not errors:
                await self.async_set_unique_id(system_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"name": reauth_entry.title},
        )
