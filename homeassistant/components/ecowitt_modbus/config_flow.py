"""Adding an Ecowitt sensor array by model and address."""

from collections.abc import Mapping
import logging
from typing import Any, override

from ecowitt_modbus import SUPPORTED_MODELS, EcowittDevice, NotThisDeviceError
from modbus_connection import ModbusError, ModbusTcpParams
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import CONF_UNIT_ID, DEFAULT_PORT, DOMAIN, MAX_UNIT_ID, MODEL_OPTIONS

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODEL): SelectSelector(
            SelectSelectorConfig(
                options=sorted(MODEL_OPTIONS),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="model",
            )
        ),
    }
)


def _connection_schema(default_unit_id: int, defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the address form, seeded from ``defaults`` where it has a value.

    ``defaults`` carries the existing settings when reconfiguring, so the
    user amends what is there instead of retyping it.
    """
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)
            ): TextSelector(),
            vol.Required(
                CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)
            ): vol.All(
                NumberSelector(
                    NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
                ),
                vol.Coerce(int),
            ),
            vol.Required(
                CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, default_unit_id)
            ): vol.All(
                NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.BOX, min=1, max=MAX_UNIT_ID
                    )
                ),
                vol.Coerce(int),
            ),
        }
    )


async def _async_probe(
    hass: HomeAssistant, model: str, user_input: Mapping[str, Any]
) -> EcowittDevice:
    """Read the device at this address and confirm it is the chosen model.

    Raises the same errors the library and transport do, for the caller to
    turn into form errors.
    """
    params = ModbusTcpParams(
        host=user_input[CONF_HOST], port=user_input[CONF_PORT], framer="rtu"
    )
    async with async_get_temporary_unit(hass, params, user_input[CONF_UNIT_ID]) as unit:
        device = SUPPORTED_MODELS[model](unit)
        await device.async_probe()
        return device


def _title(model: str, user_input: Mapping[str, Any]) -> str:
    """Name the entry for the model and where it is reached."""
    return f"{model} ({user_input[CONF_HOST]})"


def _address(model: str, user_input: Mapping[str, Any]) -> dict[str, Any]:
    """The settings that together say which device an entry talks to.

    Two entries sharing all of these would poll the same device, which is
    the duplicate a model with no serial number can still be checked for.
    """
    return {
        CONF_MODEL: model,
        CONF_HOST: user_input[CONF_HOST],
        CONF_PORT: user_input[CONF_PORT],
        CONF_UNIT_ID: user_input[CONF_UNIT_ID],
    }


class EcowittModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecowitt Modbus."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._model: str = ""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which model is being added.

        Neither sensor announces itself, and their register maps overlap
        enough that probing for one at the other's address can succeed
        misleadingly, so the model is asked for rather than guessed.
        """
        if user_input is not None:
            self._model = MODEL_OPTIONS[user_input[CONF_MODEL]]
            return await self.async_step_connection()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for an address and check the chosen model answers there."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                device = await _async_probe(self.hass, self._model, user_input)
            except NotThisDeviceError:
                errors["base"] = "wrong_model"
            except ModbusError, HomeAssistantError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if (serial := device.serial_number) is not None:
                    # Identifies the hardware wherever it is reached, so the
                    # same sensor cannot be added twice at two addresses.
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_configured()
                else:
                    # No identity to key on, so the entry gets none: an
                    # address would go stale the moment the device moved.
                    # All that can be checked is that no other entry is
                    # already polling this address.
                    self._async_abort_entries_match(_address(self._model, user_input))

                return self.async_create_entry(
                    title=_title(self._model, user_input),
                    data={CONF_MODEL: self._model, **user_input},
                )

        return self.async_show_form(
            step_id="connection",
            data_schema=_connection_schema(
                SUPPORTED_MODELS[self._model].DEFAULT_UNIT_ID, user_input or {}
            ),
            description_placeholders={"model": self._model},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change where an already-configured sensor array is reached.

        The model is fixed: a different model is a different device, and
        would be added as its own entry rather than reconfigured into this
        one.
        """
        entry = self._get_reconfigure_entry()
        model: str = entry.data[CONF_MODEL]
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                device = await _async_probe(self.hass, model, user_input)
            except NotThisDeviceError:
                errors["base"] = "wrong_model"
            except ModbusError, HomeAssistantError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if (serial := device.serial_number) is not None:
                    # Repointing an entry at a different sensor array would
                    # silently rehome its history, so a model that reports
                    # an identity has to report the same one.
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_mismatch(reason="another_device")
                else:
                    # Nothing identifies this model, so a move can only be
                    # taken on trust. All that can be checked is that the
                    # new address is not one another entry already polls.
                    self._async_abort_entries_match(_address(model, user_input))

                # The title carries the host, so it has to move with the
                # entry; leaving it would keep showing the old address.
                return self.async_update_reload_and_abort(
                    entry,
                    title=_title(model, user_input),
                    data={CONF_MODEL: model, **user_input},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(
                SUPPORTED_MODELS[model].DEFAULT_UNIT_ID, user_input or entry.data
            ),
            description_placeholders={"model": model},
            errors=errors,
        )
