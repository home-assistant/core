"""Config flow for Acaia integration."""

from typing import Any

from pyacaia_async.exceptions import AcaiaDeviceNotFound, AcaiaError, AcaiaUnknownDevice
from pyacaia_async.helpers import is_new_scale
import voluptuous as vol

from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MAC, CONF_NAME

from .const import CONF_IS_NEW_STYLE_SCALE, DOMAIN


class AcaiaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for acaia."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}

        if user_input is not None:
            if self.source == SOURCE_USER:
                try:
                    user_input[CONF_IS_NEW_STYLE_SCALE] = await is_new_scale(
                        user_input[CONF_MAC]
                    )
                except AcaiaDeviceNotFound:
                    errors["base"] = "device_not_found"
                except AcaiaError:
                    errors["base"] = "unknown"
                except AcaiaUnknownDevice:
                    return self.async_abort(reason="unsupported_device")

            if not errors:
                if self.source == SOURCE_USER:
                    await self.async_set_unique_id(user_input[CONF_MAC])
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="acaia",
                    data={
                        **self._discovered,
                        **user_input,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAC): str,
                },
            ),
            errors=errors,
        )

    async def async_step_bluetooth(self, discovery_info) -> ConfigFlowResult:
        """Handle a discovered Bluetooth device."""

        self._discovered[CONF_MAC] = discovery_info.address
        self._discovered[CONF_NAME] = discovery_info.name

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        try:
            self._discovered[CONF_IS_NEW_STYLE_SCALE] = await is_new_scale(
                discovery_info.address
            )
        except AcaiaDeviceNotFound:
            return self.async_abort(reason="device_not_found")
        except AcaiaError:
            return self.async_abort(reason="unknown")
        except AcaiaUnknownDevice:
            return self.async_abort(reason="unsupported_device")

        self._set_confirm_only()
        return self.async_show_form(step_id="user")
