"""Config flow for Airgradient."""
from typing import Any

from airgradient import AirGradientClient, AirGradientError
from airgradient.models import Status
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class AirGradientConfigFlow(ConfigFlow, domain=DOMAIN):
    """AirGradient config flow."""

    host: str | None = None
    device_status: Status | None = None

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.host = discovery_info.host

        session = async_get_clientsession(self.hass)
        air_gradient = AirGradientClient(self.host, session=session)
        self.device_status = await air_gradient.get_status()

        await self.async_set_unique_id(self.device_status.serial_number)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self.host},
            error="already_configured_device",
        )
        self.context.update(
            {
                "host": self.host,
                "title_placeholders": {
                    "model": self.device_status.serial_number,
                },
            }
        )
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self.device_status is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self.device_status.serial_number,
                data={CONF_HOST: self.host},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "model": self.device_status.serial_number,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            session = async_get_clientsession(self.hass)
            air_gradient = AirGradientClient(user_input[CONF_HOST], session=session)
            try:
                device_status = await air_gradient.get_status()
            except AirGradientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_status.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_status.serial_number,
                    data={CONF_HOST: user_input[CONF_HOST]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
