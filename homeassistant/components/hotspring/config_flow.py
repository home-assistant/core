"""Config flow for Hot Spring."""

from typing import Any, override

from hotspring import HotSpring, HotSpringConnectionError, HotSpringError, Spa
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class HotSpringConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hot Spring."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            try:
                spa = await self._async_get_spa(user_input[CONF_HOST])
            except HotSpringConnectionError, HotSpringError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    spa.info.mac_address, raise_on_progress=False
                )
                if self.source == SOURCE_RECONFIGURE:
                    entry = self._get_reconfigure_entry()
                    assert entry.unique_id is not None
                    self._abort_if_unique_id_mismatch(
                        reason="unique_id_mismatch",
                        description_placeholders={
                            "expected_mac": entry.unique_id.upper(),
                            "actual_mac": spa.info.mac_address.upper(),
                        },
                    )
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={CONF_HOST: user_input[CONF_HOST]},
                    )
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=spa.info.hostname or "Hot Spring Spa",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

        data_schema = vol.Schema({vol.Required(CONF_HOST): str})
        if self.source == SOURCE_RECONFIGURE:
            data_schema = self.add_suggested_values_to_schema(
                data_schema,
                self._get_reconfigure_entry().data,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the Hot Spring spa."""
        return await self.async_step_user(user_input)

    async def _async_get_spa(self, host: str) -> Spa:
        """Get information from a Hot Spring spa."""
        api = HotSpring(host, session=async_get_clientsession(self.hass))
        return await api.update()
