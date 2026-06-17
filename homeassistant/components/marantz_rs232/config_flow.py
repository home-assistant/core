"""Config flow for the Marantz RS-232 integration."""

from typing import Any

from marantz_rs232 import (
    MarantzV2003Receiver,
    MarantzV2007Receiver,
    MarantzV2015Receiver,
    V2007Model,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_MODEL
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
)

from .const import DOMAIN, LOGGER

MODEL_MODERN = "modern"
MODEL_SR7002 = "sr7002"
MODEL_SR8002 = "sr8002"
MODEL_SR9300 = "sr9300"
MODEL_SR8300 = "sr8300"

MODEL_NAMES: dict[str, str] = {
    MODEL_MODERN: "Modern",
    MODEL_SR7002: "SR7002",
    MODEL_SR8002: "SR8002",
    MODEL_SR9300: "SR9300",
    MODEL_SR8300: "SR8300",
}

V2007_MODELS: dict[str, V2007Model] = {
    MODEL_SR7002: V2007Model.SR7002,
    MODEL_SR8002: V2007Model.SR8002,
}

V2003_MODELS = frozenset({MODEL_SR9300, MODEL_SR8300})


async def _async_attempt_connect(port: str, model_key: str) -> str | None:
    """Attempt to connect to the receiver at the given port.

    Returns None on success, error on failure.
    """
    receiver: MarantzV2015Receiver | MarantzV2007Receiver | MarantzV2003Receiver
    if model_key == MODEL_MODERN:
        receiver = MarantzV2015Receiver(port)
    elif model_key in V2003_MODELS:
        receiver = MarantzV2003Receiver(port)
    else:
        receiver = MarantzV2007Receiver(port, model=V2007_MODELS[model_key])

    try:
        await receiver.connect()
    except (
        # When the port contains invalid connection data
        ValueError,
        # If it is a remote port, and we cannot connect
        ConnectionError,
        OSError,
        TimeoutError,
    ):
        return "cannot_connect"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected exception")
        return "unknown"
    else:
        await receiver.disconnect()
        return None


class MarantzRS232ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Marantz RS-232."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            model_key = user_input[CONF_MODEL]

            self._async_abort_entries_match({CONF_DEVICE: user_input[CONF_DEVICE]})
            error = await _async_attempt_connect(user_input[CONF_DEVICE], model_key)
            if not error:
                return self.async_create_entry(
                    title=MODEL_NAMES[model_key],
                    data={
                        CONF_DEVICE: user_input[CONF_DEVICE],
                        CONF_MODEL: model_key,
                    },
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_MODEL, default=MODEL_MODERN): SelectSelector(
                            SelectSelectorConfig(
                                options=list(MODEL_NAMES),
                                mode=SelectSelectorMode.DROPDOWN,
                                translation_key="model",
                            )
                        ),
                        vol.Required(CONF_DEVICE): SerialPortSelector(),
                    }
                ),
                user_input or {},
            ),
            errors=errors,
        )
