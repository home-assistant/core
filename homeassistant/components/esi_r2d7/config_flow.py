"""Config flow for the ESI R2D7 integration."""

from typing import Any, override

from esi_r2d7 import (
    CONNECT_ERRORS,
    MAX_CHANNEL,
    MAX_SYSTEM,
    MIN_CHANNEL,
    MIN_SYSTEM,
    R2D7Connection,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
)

from .const import CONF_FIRST_CHANNEL, CONF_LAST_CHANNEL, CONF_SYSTEM, DOMAIN, LOGGER


def _number(minimum: int, maximum: int) -> NumberSelector:
    """Return a whole-number box for the given range."""
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX
        )
    )


async def _async_attempt_connect(port: str, system: int) -> str | None:
    """Attempt to open the serial port.

    Returns None on success, error on failure. The R2D7 never answers, so this
    only proves the port opens, not that a controller is attached.
    """
    connection = R2D7Connection(port, system)

    try:
        await connection.connect()
    except (*CONNECT_ERRORS, HomeAssistantError):
        # HomeAssistantError: an ESPHome proxy port is not ready yet
        return "cannot_connect"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected exception")
        return "unknown"
    else:
        await connection.disconnect()
        return None


class EsiR2D7ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ESI R2D7."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                CONF_DEVICE: user_input[CONF_DEVICE],
                CONF_SYSTEM: int(user_input[CONF_SYSTEM]),
                CONF_FIRST_CHANNEL: int(user_input[CONF_FIRST_CHANNEL]),
                CONF_LAST_CHANNEL: int(user_input[CONF_LAST_CHANNEL]),
            }
            self._async_abort_entries_match({CONF_DEVICE: data[CONF_DEVICE]})
            if data[CONF_FIRST_CHANNEL] > data[CONF_LAST_CHANNEL]:
                errors["base"] = "invalid_channel_range"
            elif not (
                error := await _async_attempt_connect(
                    data[CONF_DEVICE], data[CONF_SYSTEM]
                )
            ):
                return self.async_create_entry(
                    title=f"ESI R2D7 system {data[CONF_SYSTEM]}", data=data
                )
            else:
                errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_DEVICE): SerialPortSelector(),
                        probatio.Required(CONF_SYSTEM, default=1): _number(
                            MIN_SYSTEM, MAX_SYSTEM
                        ),
                        probatio.Required(CONF_FIRST_CHANNEL, default=1): _number(
                            MIN_CHANNEL, MAX_CHANNEL
                        ),
                        probatio.Required(CONF_LAST_CHANNEL, default=16): _number(
                            MIN_CHANNEL, MAX_CHANNEL
                        ),
                    }
                ),
                user_input or {},
            ),
            errors=errors,
        )
