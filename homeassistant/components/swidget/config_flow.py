"""Config flow for swidget integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from swidget.exceptions import SwidgetException
from swidget.swidgetdevice import SwidgetDevice
import voluptuous as vol  # type: ignore[import-untyped]

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_INTERVAL = timedelta(minutes=15)
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    device: SwidgetDevice = SwidgetDevice(
        host=data["host"],
        token_name="x-secret-key",
        secret_key=data.get("password"),
        use_https=True,
        use_websockets=False,
    )
    try:
        await device.update()
        await device.stop()
    except SwidgetException as exc:
        raise CannotConnect from exc
    friendly_name: str = device.friendly_name
    unique_id: str = f"{device.id}_{device.mac_address}"
    return {"title": friendly_name, "unique_id": unique_id}


class SwidgetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for swidget."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                unique_id = info["unique_id"]
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unable to validate Swidget device credentials")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidHost(HomeAssistantError):
    """Error to indicate the host is not valid."""


class TimeoutConnect(HomeAssistantError):
    """Error to indicate the connection attempt is timed out."""
