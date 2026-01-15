"""Config flow for Dexcom integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pydexcom import Dexcom, Region
from pydexcom.errors import AccountError, DexcomError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.helpers import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_REGION, default=Region.US): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(Region), translation_key=CONF_REGION
            ),
        ),
    }
)


class DexcomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dexcom."""

    VERSION = 2

    async def _validate_user_input(
        self, user_input: Mapping[str, Any], errors: dict[str, str]
    ) -> Dexcom | None:
        """Validate the input data."""
        try:
            return await self.hass.async_add_executor_job(
                lambda: Dexcom(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    region=user_input[CONF_REGION],
                )
            )
        except AccountError:
            errors["base"] = "invalid_auth"
        except DexcomError:
            _LOGGER.exception("Dexcom error")
            errors["base"] = "unknown"
        except Exception:
            _LOGGER.exception("Unknown error")
            errors["base"] = "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            dexcom = await self._validate_user_input(user_input, errors)
            if dexcom is not None:
                await self.async_set_unique_id(dexcom.account_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
