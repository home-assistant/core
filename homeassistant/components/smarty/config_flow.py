"""Config flow for Smarty integration."""

from typing import Any

from pysmarty2 import Smarty
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME


class SmartyConfigFlow(ConfigFlow):
    """Smarty config flow."""

    def _test_connection(self, host: str) -> bool:
        """Test the connection to the Smarty API."""
        smarty = Smarty(host=host)
        return smarty.update()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)
            try:
                if self.hass.async_add_executor_job(
                    self._test_connection, user_input[CONF_HOST]
                ):
                    return self.async_create_entry(
                        title=user_input[CONF_HOST], data=user_input
                    )
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow initialized by import."""
        self._async_abort_entries_match({CONF_HOST: import_config[CONF_HOST]})
        try:
            if self.hass.async_add_executor_job(
                self._test_connection, import_config[CONF_HOST]
            ):
                return self.async_create_entry(
                    title=import_config[CONF_NAME],
                    data={CONF_HOST: import_config[CONF_HOST]},
                )
            error = "cannot_connect"
        except Exception:  # noqa: BLE001
            error = "unknown"
        return self.async_abort(reason=error)
