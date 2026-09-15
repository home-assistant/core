"""Config flow for the pretalx integration."""

import logging
from typing import Any, override

import probatio as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EVENT, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import PretalxClient, PretalxError, PretalxEventNotFound

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_EVENT): str,
    }
)


class PretalxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pretalx."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            event = user_input[CONF_EVENT]
            await self.async_set_unique_id(f"{url}_{event}")
            self._abort_if_unique_id_configured()

            client = PretalxClient(async_get_clientsession(self.hass), url, event)
            try:
                event_data = await client.async_get_event()
            except PretalxEventNotFound:
                errors["base"] = "event_not_found"
            except PretalxError:
                errors["base"] = "cannot_connect"
            else:
                name = event_data["name"]
                if isinstance(name, dict):
                    name = next(iter(name.values()), event)
                return self.async_create_entry(
                    title=name,
                    data={CONF_URL: url, CONF_EVENT: event},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
