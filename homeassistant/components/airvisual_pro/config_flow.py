"""Define a config flow manager for AirVisual Pro."""
from __future__ import annotations

from pyairvisual import NodeSamba
from pyairvisual.node import NodeProError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, LOGGER

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class AirVisualProFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an AirVisual Pro config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if not user_input:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

        await self.async_set_unique_id(user_input[CONF_IP_ADDRESS])
        self._abort_if_unique_id_configured()

        errors = {}
        node = NodeSamba(user_input[CONF_IP_ADDRESS], user_input[CONF_PASSWORD])

        try:
            await node.async_connect()
        except NodeProError as err:
            LOGGER.error(
                "Samba error while connecting to %s: %s",
                user_input[CONF_IP_ADDRESS],
                err,
            )
            errors["base"] = "cannot_connect"
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.error(
                "Unknown error while connecting to %s: %s",
                user_input[CONF_IP_ADDRESS],
                err,
            )
            errors["base"] = "unknown"
        finally:
            await node.async_disconnect()

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
            )

        return self.async_create_entry(
            title=user_input[CONF_IP_ADDRESS], data=user_input
        )
