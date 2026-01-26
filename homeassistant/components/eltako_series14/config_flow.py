"""Config flows for the Eltako Series 14 integration."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from typing import Any

import serial
import serial.tools.list_ports
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import SchemaFlowError

from .const import (
    CONF_FAST_STATUS_CHANGE,
    CONF_GATEWAY_AUTO_RECONNECT,
    CONF_GATEWAY_MESSAGE_DELAY,
    CONF_SENDER_ID,
    CONF_SERIAL_PORT,
    DOMAIN,
    ID_REGEX,
)
from .device import GATEWAY_MODELS, SWITCH_MODELS, ModelDefinition
from .gateway import EltakoGateway

_LOGGER = logging.getLogger(__name__)
_SERIAL_VALIDATE_TIMEOUT = 0.1


def _validate_enocean_id(user_input: dict[str, Any], key: str) -> None:
    try:
        cv.matches_regex(ID_REGEX)(user_input[key])
    except vol.Invalid as e:
        raise InvalidIdFormat from e


def _validate_sender(user_input: dict[str, Any]) -> None:
    try:
        _validate_enocean_id(user_input, CONF_SENDER_ID)
    except InvalidIdFormat as e:
        raise InvalidSenderIdFormat from e


def _validate_gateway_path(user_input: dict[str, Any]) -> None:
    """Return True if the provided path points to a valid serial port, False otherwise."""

    try:
        serial.serial_for_url(
            url=user_input[CONF_SERIAL_PORT],
            baudrate=GATEWAY_MODELS[user_input[CONF_MODEL]].baud_rate,
            timeout=_SERIAL_VALIDATE_TIMEOUT,
        )
    except serial.SerialException as e:
        raise InvalidGatewayPath from e


async def _async_validate_gateway(user_input: dict[str, Any]) -> None:
    """Return True if the gateway can be accessed."""
    gateway = EltakoGateway(
        GATEWAY_MODELS[user_input[CONF_MODEL]],
        user_input[CONF_SERIAL_PORT],
        user_input[CONF_GATEWAY_AUTO_RECONNECT],
        user_input[CONF_GATEWAY_MESSAGE_DELAY],
        user_input[CONF_FAST_STATUS_CHANGE],
    )
    await gateway.async_setup()
    gateway.unload()


def _get_model_options(models: Mapping[str, ModelDefinition]) -> dict[str, str]:
    return {key: model.name for key, model in models.items()}


class EltakoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle the Eltako config flows."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure an Eltako Gateway."""
        errors: dict[str, str] = {}

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        serial_ports = {p.device: f"{p.description} ({p.device})" for p in ports}
        if not serial_ports:
            return self.async_abort(reason="no_serial_ports")

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT]}
            )
            try:
                _validate_enocean_id(user_input, CONF_ID)
                _validate_gateway_path(user_input)
                await _async_validate_gateway(user_input)
            except InvalidIdFormat:
                errors[CONF_ID] = "invalid_id"
            except InvalidGatewayPath:
                errors[CONF_SERIAL_PORT] = "invalid_gateway_path"
            except RuntimeError:
                errors[CONF_SERIAL_PORT] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception: %s")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        title=user_input[CONF_NAME],
                        data_updates=user_input,
                    )
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Eltako Gateway"): str,
                vol.Required(CONF_ID, default="00-00-B0-00"): str,
                vol.Required(CONF_MODEL): vol.In(_get_model_options(GATEWAY_MODELS)),
                vol.Required(CONF_SERIAL_PORT): vol.In(serial_ports),
                vol.Required(CONF_GATEWAY_AUTO_RECONNECT, default=True): bool,
                vol.Required(CONF_FAST_STATUS_CHANGE, default=True): bool,
                vol.Required(CONF_GATEWAY_MESSAGE_DELAY, default=0.01): vol.All(
                    vol.Coerce(float), vol.Range(min=0.0)
                ),
            }
        )

        if user_input:
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)
        elif self.source == SOURCE_RECONFIGURE:
            data_schema = self.add_suggested_values_to_schema(
                data_schema, self._get_reconfigure_entry().data
            )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors, last_step=True
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure an Eltako Gateway."""
        return await self.async_step_user(user_input)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"device": DeviceSubentryFlowHandler}


@dataclass(frozen=True)
class DeviceTypeConfig:
    """A class to configure the different Eltako device types, that can be set up."""

    step_name: str
    models: Mapping[str, ModelDefinition]
    extra_schema: dict[vol.Marker, Any]
    extra_validate: Callable[[dict[str, Any]], None]


class DeviceSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying an device."""

    def _error_entries_match(self, user_input: dict[str, Any]) -> None:
        for subentry in self._get_entry().subentries.values():
            if self.source == SOURCE_RECONFIGURE:
                if subentry == self._get_reconfigure_subentry():
                    continue
            if str(user_input[CONF_ID]).lower() == str(subentry.data[CONF_ID]).lower():
                raise AlreadyConfigured

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select the devoce type to add."""
        return self.async_show_menu(step_id="user", menu_options=["switch"])

    async def async_step_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a switch device."""
        device_type_config = DeviceTypeConfig(
            step_name="switch",
            models=SWITCH_MODELS,
            extra_schema={vol.Required(CONF_SENDER_ID, default="00-00-B0-01"): str},
            extra_validate=_validate_sender,
        )
        return await self._async_step_device_type(device_type_config, user_input)

    async def _async_step_device_type(
        self, device_type_config: DeviceTypeConfig, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._error_entries_match(user_input)
                _validate_enocean_id(user_input, CONF_ID)
                device_type_config.extra_validate(user_input)
            except InvalidSenderIdFormat:
                errors[CONF_SENDER_ID] = "invalid_id"
            except InvalidIdFormat:
                errors[CONF_ID] = "invalid_id"
            except AlreadyConfigured:
                errors[CONF_ID] = "already_configured"
            else:
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_and_abort(
                        self._get_entry(),
                        self._get_reconfigure_subentry(),
                        title=user_input[CONF_NAME],
                        data_updates=user_input,
                    )
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        model_options = _get_model_options(device_type_config.models)
        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_ID, default="00-00-00-01"): str,
                vol.Required(CONF_MODEL): vol.In(model_options),
            }
        )
        data_schema = data_schema.extend(device_type_config.extra_schema)

        if user_input:
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)
        elif self.source == SOURCE_RECONFIGURE:
            data_schema = self.add_suggested_values_to_schema(
                data_schema, self._get_reconfigure_subentry().data
            )

        return self.async_show_form(
            step_id=device_type_config.step_name,
            data_schema=data_schema,
            errors=errors,
            last_step=True,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to modify an existing device."""
        config_subentry = self._get_reconfigure_subentry()
        model_key = config_subentry.data[CONF_MODEL]
        if model_key in SWITCH_MODELS:
            return await self.async_step_switch()
        return self.async_abort(reason="model_not_found")


class InvalidGatewayPath(SchemaFlowError):
    """Error to indicate there is invalid gateway path."""


class AlreadyConfigured(SchemaFlowError):
    """Error to indicate that this device has already been configured."""


class InvalidIdFormat(SchemaFlowError):
    """Error to indicate that the ID has an invalid format."""


class InvalidSenderIdFormat(InvalidIdFormat):
    """Error to indicate that the sender ID has an invalid format."""
