"""TFA.me station integration: config_flow.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

import logging
from typing import Any, override

from tfa_me_ha_local.client import (
    TFAmeConnectionError,
    TFAmeException,
    TFAmeHTTPError,
    TFAmeJSONError,
    TFAmeTimeoutError,
)
from tfa_me_ha_local.validators import TFAmeValidator
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS

from .const import DEFAULT_STATION_NAME, DOMAIN
from .data import TFAmeUniqueID

_LOGGER = logging.getLogger(__name__)


class TFAmeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for TFA.me stations."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}

        data_schema = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS, default=""): str,
            }
        )

        if user_input is not None:
            ip_host_str = user_input.get(CONF_IP_ADDRESS)
            validator = TFAmeValidator()

            if validator.is_valid_ip_or_tfa_me(ip_host_str):
                title_str = DEFAULT_STATION_NAME
                if isinstance(ip_host_str, str):
                    title_str = f"{DEFAULT_STATION_NAME} '{ip_host_str.upper()}'"

                try:
                    data_helper = TFAmeUniqueID(self.hass, str(ip_host_str))
                    identifier = await data_helper.get_identifier()

                except TFAmeTimeoutError:
                    errors["base"] = "timeout_connect"
                except TFAmeConnectionError:
                    errors["base"] = "cannot_connect"
                except TFAmeHTTPError, TFAmeJSONError:
                    errors["base"] = "invalid_response"
                except TFAmeException:
                    errors["base"] = "unknown"
                except Exception:
                    _LOGGER.exception(
                        "Unexpected exception while validating TFA.me host"
                    )
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(identifier)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(title=title_str, data=user_input)
            else:
                errors[CONF_IP_ADDRESS] = "invalid_ip_host"

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
