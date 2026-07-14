"""Config flow for LinknLink."""

import re
from typing import Any, override

from aiolinknlink import DISPLAY_MODEL_ULTRA, UltraClient, UltraDevice, UltraError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DEFAULT_PORT, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_MAC): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


class LinknLinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LinknLink."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle setup initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = dr.format_mac(user_input[CONF_MAC].strip())
            if not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", mac):
                errors[CONF_MAC] = "invalid_mac"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                port = user_input[CONF_PORT]
                device = UltraDevice(
                    id=mac,
                    ip=user_input[CONF_HOST],
                    port=port,
                    mac=mac,
                    model=DISPLAY_MODEL_ULTRA,
                )
                try:
                    session = await UltraClient(default_port=port).connect(device)
                except UltraError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    LOGGER.exception(
                        "Unexpected exception while connecting to LinknLink"
                    )
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=session.device.model,
                        data={
                            CONF_HOST: user_input[CONF_HOST],
                            CONF_MAC: mac,
                            CONF_PORT: port,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
