"""Config flow for the LG TV RS-232 integration."""

from typing import Any

from lg_rs232_tv import DEFAULT_SET_ID, LGTV, TVNotRespondingError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
)

from .const import CONF_SET_ID, DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialPortSelector(),
        vol.Required(CONF_SET_ID, default=DEFAULT_SET_ID): NumberSelector(
            NumberSelectorConfig(min=1, max=99, mode=NumberSelectorMode.BOX)
        ),
    }
)

# Outcome of _async_attempt_connect that means the serial port works but no LG
# TV answered it; this routes the user to the troubleshooting step.
RESULT_NO_TV = "no_tv"


async def _async_attempt_connect(port: str, set_id: int) -> str | None:
    """Attempt to connect to the TV at the given port.

    Returns None on success, otherwise an outcome key: "cannot_connect" when
    the serial port could not be opened, RESULT_NO_TV when the port works but
    no LG TV responded to it, or "unknown" for an unexpected error.
    """
    tv = LGTV(port, set_id=set_id)

    try:
        await tv.connect()
    except TVNotRespondingError:
        # The port was opened but no LG TV responded to the power query.
        return RESULT_NO_TV
    except ValueError, ConnectionError, OSError, TimeoutError:
        # The serial port itself could not be opened.
        return "cannot_connect"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected exception")
        return "unknown"
    else:
        await tv.disconnect()
        return None


class LGTVRS232ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LG TV RS-232."""

    VERSION = 1

    _user_input: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            port = user_input[CONF_DEVICE]
            set_id = int(user_input[CONF_SET_ID])

            self._async_abort_entries_match({CONF_DEVICE: port, CONF_SET_ID: set_id})
            error = await _async_attempt_connect(port, set_id)
            if error is None:
                return self.async_create_entry(
                    title="LG TV",
                    data={CONF_DEVICE: port, CONF_SET_ID: set_id},
                )
            if error == RESULT_NO_TV:
                self._user_input = user_input
                return await self.async_step_troubleshoot()
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input or self._user_input or {}
            ),
            errors=errors,
        )

    async def async_step_troubleshoot(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Guide the user to enable RS-232 control after a failed connection."""
        if user_input is not None:
            return await self.async_step_user()

        return self.async_show_form(step_id="troubleshoot")
