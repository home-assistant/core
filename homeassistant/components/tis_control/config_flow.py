"""Config flow for TIS Control integration."""

import contextlib
import logging
from typing import override

import probatio
from TISApi.api import TISApi

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PORT
from homeassistant.core import callback

from .const import DEVICES_DICT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TISConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TIS Control."""

    @override
    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            unique_id = f"{DOMAIN}:{user_input[CONF_PORT]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            error = await self.validate_input(user_input)

            if error == "no_devices_found":
                return self.async_abort(reason="no_devices_found")

            if error:
                errors["base"] = error
                return self._show_setup_form(errors=errors)

            _LOGGER.debug("Received user input %s", user_input)
            return self.async_create_entry(title="TIS Control Bridge", data=user_input)

        # If user_input is None (initial step), show the setup form
        return self._show_setup_form(errors=errors)

    @callback
    def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""

        schema = probatio.Schema(
            {
                probatio.Required(CONF_PORT, default=6000): probatio.All(
                    int, probatio.Range(min=1, max=65535)
                )
            },
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors or {},
        )

    async def validate_input(self, data: dict) -> str | None:
        """Validate the user input allows us to connect and discover devices."""
        tis_api = TISApi(
            port=int(data[CONF_PORT]),
            domain=DOMAIN,
            devices_dict=DEVICES_DICT,
        )
        try:
            await tis_api.connect()
            await tis_api.scan_devices()
            if not tis_api.devices:
                return "no_devices_found"
        except (ConnectionError, OSError) as e:
            _LOGGER.debug(
                "Failed to connect to TIS Control bridge at %d: %s", data[CONF_PORT], e
            )
            return "cannot_connect"
        except Exception:
            _LOGGER.exception(
                "Unexpected error while validating TIS Control connection"
            )
            return "unknown"
        finally:
            with contextlib.suppress(Exception):
                tis_api.disconnect()

        return None
