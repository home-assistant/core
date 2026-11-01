"""Config flow for the Marantz RS-232 integration."""

from typing import Any, override

from marantz_rs232 import MarantzV2007Receiver
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.helpers.selector import SerialPortSelector

from .const import DEFAULT_NAME, DOMAIN, LOGGER


async def _async_attempt_connect(port: str) -> str | None:
    """Attempt to connect to the receiver at the given port."""
    receiver = MarantzV2007Receiver(port)
    try:
        await receiver.connect()
    except ValueError, ConnectionError, OSError, TimeoutError:
        return "cannot_connect"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected exception")
        return "unknown"
    finally:
        if receiver.connected:
            await receiver.disconnect()
    return None


class MarantzRS232ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Marantz RS-232."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_DEVICE: user_input[CONF_DEVICE]})
            error = await _async_attempt_connect(user_input[CONF_DEVICE])
            if error is None:
                return self.async_create_entry(
                    title=DEFAULT_NAME, data={CONF_DEVICE: user_input[CONF_DEVICE]}
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema({probatio.Required(CONF_DEVICE): SerialPortSelector()}),
                user_input or {},
            ),
            errors=errors,
        )
