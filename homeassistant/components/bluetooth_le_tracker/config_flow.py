"""Config flow for Bluetooth LE Tracker."""

from typing import override

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class BluetoothLETrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bluetooth LE Tracker."""

    VERSION = 1

    @override
    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="Bluetooth LE Tracker",
                data={},
            )

        return self.async_show_form(step_id="user")
