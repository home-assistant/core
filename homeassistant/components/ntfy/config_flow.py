"""Config flow for the ntfy integration."""

from __future__ import annotations

import logging
import random
import string
from typing import Any

from aiontfy import Message, Ntfy
from aiontfy.exceptions import NtfyException, NtfyForbiddenAccessError, NtfyHTTPError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_TOPIC, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Optional(CONF_TOPIC): str,
    }
)


class NtfyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ntfy."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_TOPIC):
                user_input[CONF_TOPIC] = "".join(
                    random.choices(
                        string.ascii_lowercase + string.ascii_uppercase + string.digits,
                        k=16,
                    )
                )
            self._async_abort_entries_match(user_input)
            try:
                session = async_get_clientsession(self.hass)
                ntfy = Ntfy(user_input[CONF_URL], session)
                await ntfy.publish(
                    Message(
                        topic=user_input[CONF_TOPIC],
                        title="Home Assistant",
                        message="The Home Assistant ntfy integration has been successfully set up for this topic.",
                    )
                )
            except NtfyForbiddenAccessError:
                errors["base"] = "forbidden_topic"
            except NtfyHTTPError as e:
                _LOGGER.debug("Error %s: %s [%s]", e.code, e.error, e.link)
                errors["base"] = "cannot_connect"
            except NtfyException:
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_url"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_TOPIC], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
