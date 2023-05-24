"""Config flow for Anova."""
from __future__ import annotations

from anova_wifi import AnovaApi, InvalidLogin, NoDevicesFound
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .util import serialize_device_list


class AnovaConfligFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Sets up a config flow for Anova."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api = AnovaApi(
                aiohttp_client.async_get_clientsession(self.hass),
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()
            try:
                await api.authenticate()
                devices = await api.get_devices()
            except InvalidLogin:
                errors["base"] = "invalid_auth"
            except NoDevicesFound:
                errors["base"] = "no_devices_found"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                # We store device list in config flow in order to persist found devices on restart, as the Anova api get_devices does not return any devices that are offline.
                device_list = serialize_device_list(devices)
                return self.async_create_entry(
                    title="Anova",
                    data={
                        CONF_USERNAME: api.username,
                        CONF_PASSWORD: api.password,
                        "devices": device_list,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )
