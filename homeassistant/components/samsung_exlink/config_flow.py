"""Config flow for the Samsung ExLink integration."""

from typing import Any

from samsung_exlink import MODELS, SamsungTV, SamsungTVError, TVModel
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_MODEL
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
)

from .const import DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialPortSelector(),
        vol.Optional(CONF_MODEL): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=key, label=model.name)
                    for key, model in MODELS.items()
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)

# Outcome of _async_attempt_connect that means the serial port works but no
# Samsung TV answered it; this routes the user to the troubleshooting step.
RESULT_NO_TV = "no_tv"


async def _async_attempt_connect(port: str, model: TVModel | None) -> str | None:
    """Attempt to connect to the TV at the given port.

    Returns None on success, otherwise an outcome key: "cannot_connect" when
    the serial port could not be opened, RESULT_NO_TV when the port works but
    no Samsung TV responded to it, or "unknown" for an unexpected error.
    """
    tv = SamsungTV(port, model=model)

    try:
        await tv.connect()
    except ValueError, ConnectionError, OSError, TimeoutError:
        # The serial port itself could not be opened.
        return "cannot_connect"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected exception")
        return "unknown"

    try:
        await tv.query_power()
    except TimeoutError, SamsungTVError:
        # The port was opened but no Samsung TV responded to the power query.
        return RESULT_NO_TV
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected exception")
        return "unknown"
    finally:
        await tv.disconnect()

    return None


class SamsungExLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Samsung ExLink."""

    VERSION = 1

    _user_input: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            port = user_input[CONF_DEVICE]
            model_key = user_input.get(CONF_MODEL)

            self._async_abort_entries_match({CONF_DEVICE: port})
            error = await _async_attempt_connect(port, MODELS.get(model_key or ""))
            if error is None:
                return self.async_create_entry(title="Samsung TV", data=user_input)
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
        """Guide the user to enable ExLink control after a failed connection."""
        if user_input is not None:
            return await self.async_step_user()

        return self.async_show_form(step_id="troubleshoot")
