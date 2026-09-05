"""Config flow for Ecobulles integration."""

from collections.abc import Mapping
import logging
from typing import Any

from pyecobulles import EcobullesClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.dt import now as hass_now

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Validate the user input allows us to connect."""
    client = EcobullesClient(session=async_get_clientsession(hass), now_fn=hass_now)
    try:
        auth_success, user_id, eco_ref, boitier_name = await client.authenticate(
            data[CONF_EMAIL], data[CONF_PASSWORD]
        )
        if not auth_success or eco_ref is None:
            raise InvalidAuth
        device_info_raw = await client.get_device_info(eco_ref)
    except TimeoutError as err:
        raise CannotConnect from err
    except RuntimeError as err:
        raise CannotConnect from err

    device_name = (boitier_name or "").strip()
    box = (device_info_raw or {}).get("data", {}).get("boite", {})
    resolved_name = (box.get("name") or device_name or "").strip()
    return {
        "title": f"Ecobulles : {resolved_name}" if resolved_name else "Ecobulles",
        "user_id": user_id,
        "eco_ref": eco_ref,
        "name": resolved_name,
        "firmware_version": box.get("firm_ver"),
        "num_serie": box.get("num_serie"),
    }


class EcobullesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecobulles."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                entry_data = {**user_input, **info}
                title = entry_data.pop("title")
                await self.async_set_unique_id(info["eco_ref"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=entry_data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate invalid auth."""
