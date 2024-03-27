"""Config flow for godice."""

from __future__ import annotations

from godice import Shell
import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.helpers import selector

from .const import CONF_SHELL, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SHELL): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[v.name for v in Shell],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)


class GoDiceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Setup GoDice discovered via Bluetooth."""

    def __init__(self) -> None:
        """Declare fields used later on device discovery."""
        self._discovery_info: BluetoothServiceInfo | None = None

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        return self.async_abort(reason="auto_discovery_only")

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """GoDice discovery handler."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None) -> ConfigFlowResult:
        """Show setup confirmation dialog and setup when confirmed."""
        assert self._discovery_info is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name,
                data={
                    CONF_NAME: self._discovery_info.name,
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_SHELL: user_input[CONF_SHELL],
                },
            )

        self._set_confirm_only()
        self.context["title_placeholders"] = {CONF_NAME: self._discovery_info.name}
        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=DATA_SCHEMA,
            description_placeholders={
                CONF_NAME: self._discovery_info.name,
                CONF_ADDRESS: self._discovery_info.address,
            },
        )
