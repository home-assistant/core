"""Config flow for the Bambu Lab integration."""

import logging
from typing import Any, override

from aiobambulab import (
    BambuLabAuthenticationError,
    BambuLabCertificateError,
    BambuLabClient,
    BambuLabConnectionError,
    BambuLabSerialMismatchError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_ACCESS_CODE, CONF_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_SERIAL_NUMBER): TextSelector(),
        probatio.Required(probatio.Secret(CONF_ACCESS_CODE)): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class BambuLabConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bambu Lab."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = BambuLabClient(
                user_input[CONF_HOST],
                user_input[CONF_SERIAL_NUMBER],
                user_input[CONF_ACCESS_CODE],
            )
            try:
                await client.connect()
            except BambuLabAuthenticationError:
                errors["base"] = "invalid_auth"
            except BambuLabSerialMismatchError:
                errors["base"] = "serial_number_mismatch"
            except BambuLabCertificateError:
                errors["base"] = "untrusted_certificate"
            except BambuLabConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await client.disconnect()
                await self.async_set_unique_id(client.serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=client.info.model_name or client.serial,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_SERIAL_NUMBER: client.serial,
                        CONF_ACCESS_CODE: user_input[CONF_ACCESS_CODE],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
