"""Config flow for the PiKVM integration."""

from typing import Any, override

from pikvm_aio import PiKVMAuthenticationError, PiKVMDeviceInfo, PiKVMError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL

from .const import CONF_TOTP, DEFAULT_USERNAME, DOMAIN, LOGGER
from .coordinator import create_client

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
        probatio.Optional(probatio.Secret(CONF_TOTP)): str,
        probatio.Required(CONF_VERIFY_SSL, default=False): bool,
    }
)


class PiKVMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PiKVM."""

    VERSION = 1

    async def _async_validate_input(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> PiKVMDeviceInfo | None:
        """Return the device info, or None and fill in errors."""
        # A one-time 6 or 8 digit code would work once and then expire.
        totp = data.get(CONF_TOTP, "").strip().replace(" ", "")
        if len(totp) in (6, 8) and totp.isdigit():
            errors[CONF_TOTP] = "invalid_totp"
            return None
        try:
            client = create_client(self.hass, data)
        except PiKVMAuthenticationError:
            errors[CONF_TOTP] = "invalid_totp"
            return None
        except ValueError:
            errors[CONF_HOST] = "invalid_host"
            return None
        try:
            return await client.get_info()
        except PiKVMAuthenticationError:
            errors["base"] = "invalid_auth"
        except PiKVMError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            if info := await self._async_validate_input(user_input, errors):
                if not info.serial:
                    return self.async_abort(reason="missing_serial")
                await self.async_set_unique_id(info.serial)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(title=info.name, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
