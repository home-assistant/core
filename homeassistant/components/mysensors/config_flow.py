"""Config flow for MySensors."""
from __future__ import annotations

from contextlib import suppress
import logging
import os
from typing import Any

from awesomeversion import (
    AwesomeVersion,
    AwesomeVersionStrategy,
    AwesomeVersionStrategyException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.mqtt import valid_publish_topic, valid_subscribe_topic
from homeassistant.components.mysensors import (
    CONF_DEVICE,
    DEFAULT_BAUD_RATE,
    DEFAULT_TCP_PORT,
    is_persistence_file,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import CONF_RETAIN, CONF_VERSION, DEFAULT_VERSION
from .const import (
    CONF_BAUD_RATE,
    CONF_GATEWAY_TYPE,
    CONF_GATEWAY_TYPE_ALL,
    CONF_GATEWAY_TYPE_MQTT,
    CONF_GATEWAY_TYPE_SERIAL,
    CONF_GATEWAY_TYPE_TCP,
    CONF_PERSISTENCE_FILE,
    CONF_TCP_PORT,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
    DOMAIN,
    ConfGatewayType,
)
from .gateway import MQTT_COMPONENT, is_serial_port, is_socket_address, try_connect

_LOGGER = logging.getLogger(__name__)


def _get_schema_common(user_input: dict[str, str]) -> dict:
    """Create a schema with options common to all gateway types."""
    schema = {
        vol.Required(
            CONF_VERSION,
            default="",
            description={
                "suggested_value": user_input.get(CONF_VERSION, DEFAULT_VERSION)
            },
        ): str,
        vol.Optional(CONF_PERSISTENCE_FILE): str,
    }
    return schema


def _validate_version(version: str) -> dict[str, str]:
    """Validate a version string from the user."""
    version_okay = False
    with suppress(AwesomeVersionStrategyException):
        version_okay = bool(
            AwesomeVersion.ensure_strategy(
                version,
                [AwesomeVersionStrategy.SIMPLEVER, AwesomeVersionStrategy.SEMVER],
            )
        )

    if version_okay:
        return {}
    return {CONF_VERSION: "invalid_version"}


def _is_same_device(
    gw_type: ConfGatewayType, user_input: dict[str, str], entry: ConfigEntry
):
    """Check if another ConfigDevice is actually the same as user_input.

    This function only compares addresses and tcp ports, so it is possible to fool it with tricks like port forwarding.
    """
    if entry.data[CONF_DEVICE] != user_input[CONF_DEVICE]:
        return False
    if gw_type == CONF_GATEWAY_TYPE_TCP:
        return entry.data[CONF_TCP_PORT] == user_input[CONF_TCP_PORT]
    if gw_type == CONF_GATEWAY_TYPE_MQTT:
        entry_topics = {
            entry.data[CONF_TOPIC_IN_PREFIX],
            entry.data[CONF_TOPIC_OUT_PREFIX],
        }
        return (
            user_input.get(CONF_TOPIC_IN_PREFIX) in entry_topics
            or user_input.get(CONF_TOPIC_OUT_PREFIX) in entry_topics
        )
    return True


class MySensorsConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    def __init__(self) -> None:
        """Set up config flow."""
        self._gw_type: str | None = None

    async def async_step_import(self, user_input: dict[str, str] | None = None):
        """Import a config entry.

        This method is called by async_setup and it has already
        prepared the dict to be compatible with what a user would have
        entered from the frontend.
        Therefore we process it as though it came from the frontend.
        """
        if user_input[CONF_DEVICE] == MQTT_COMPONENT:
            user_input[CONF_GATEWAY_TYPE] = CONF_GATEWAY_TYPE_MQTT
        else:
            try:
                await self.hass.async_add_executor_job(
                    is_serial_port, user_input[CONF_DEVICE]
                )
            except vol.Invalid:
                user_input[CONF_GATEWAY_TYPE] = CONF_GATEWAY_TYPE_TCP
            else:
                user_input[CONF_GATEWAY_TYPE] = CONF_GATEWAY_TYPE_SERIAL

        result: dict[str, Any] = await self.async_step_user(user_input=user_input)
        if result["type"] == "form":
            return self.async_abort(reason=next(iter(result["errors"].values())))
        return result

    async def async_step_user(self, user_input: dict[str, str] | None = None):
        """Create a config entry from frontend user input."""
        schema = {vol.Required(CONF_GATEWAY_TYPE): vol.In(CONF_GATEWAY_TYPE_ALL)}
        schema = vol.Schema(schema)

        if user_input is not None:
            gw_type = self._gw_type = user_input[CONF_GATEWAY_TYPE]
            input_pass = user_input if CONF_DEVICE in user_input else None
            if gw_type == CONF_GATEWAY_TYPE_MQTT:
                return await self.async_step_gw_mqtt(input_pass)
            if gw_type == CONF_GATEWAY_TYPE_TCP:
                return await self.async_step_gw_tcp(input_pass)
            if gw_type == CONF_GATEWAY_TYPE_SERIAL:
                return await self.async_step_gw_serial(input_pass)

        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_gw_serial(self, user_input: dict[str, str] | None = None):
        """Create config entry for a serial gateway."""
        errors = {}
        if user_input is not None:
            errors.update(
                await self.validate_common(CONF_GATEWAY_TYPE_SERIAL, errors, user_input)
            )
            if not errors:
                return self._async_create_entry(user_input)

        user_input = user_input or {}
        schema = _get_schema_common(user_input)
        schema[
            vol.Required(
                CONF_BAUD_RATE,
                default=user_input.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE),
            )
        ] = cv.positive_int
        schema[
            vol.Required(
                CONF_DEVICE, default=user_input.get(CONF_DEVICE, "/dev/ttyACM0")
            )
        ] = str

        schema = vol.Schema(schema)
        return self.async_show_form(
            step_id="gw_serial", data_schema=schema, errors=errors
        )

    async def async_step_gw_tcp(self, user_input: dict[str, str] | None = None):
        """Create a config entry for a tcp gateway."""
        errors = {}
        if user_input is not None:
            if CONF_TCP_PORT in user_input:
                port: int = user_input[CONF_TCP_PORT]
                if not (0 < port <= 65535):
                    errors[CONF_TCP_PORT] = "port_out_of_range"

            errors.update(
                await self.validate_common(CONF_GATEWAY_TYPE_TCP, errors, user_input)
            )
            if not errors:
                return self._async_create_entry(user_input)

        user_input = user_input or {}
        schema = _get_schema_common(user_input)
        schema[
            vol.Required(CONF_DEVICE, default=user_input.get(CONF_DEVICE, "127.0.0.1"))
        ] = str
        # Don't use cv.port as that would show a slider *facepalm*
        schema[
            vol.Optional(
                CONF_TCP_PORT, default=user_input.get(CONF_TCP_PORT, DEFAULT_TCP_PORT)
            )
        ] = vol.Coerce(int)

        schema = vol.Schema(schema)
        return self.async_show_form(step_id="gw_tcp", data_schema=schema, errors=errors)

    def _check_topic_exists(self, topic: str) -> bool:
        for other_config in self.hass.config_entries.async_entries(DOMAIN):
            if topic == other_config.data.get(
                CONF_TOPIC_IN_PREFIX
            ) or topic == other_config.data.get(CONF_TOPIC_OUT_PREFIX):
                return True
        return False

    async def async_step_gw_mqtt(self, user_input: dict[str, str] | None = None):
        """Create a config entry for a mqtt gateway."""
        errors = {}
        if user_input is not None:
            user_input[CONF_DEVICE] = MQTT_COMPONENT

            try:
                valid_subscribe_topic(user_input[CONF_TOPIC_IN_PREFIX])
            except vol.Invalid:
                errors[CONF_TOPIC_IN_PREFIX] = "invalid_subscribe_topic"
            else:
                if self._check_topic_exists(user_input[CONF_TOPIC_IN_PREFIX]):
                    errors[CONF_TOPIC_IN_PREFIX] = "duplicate_topic"

            try:
                valid_publish_topic(user_input[CONF_TOPIC_OUT_PREFIX])
            except vol.Invalid:
                errors[CONF_TOPIC_OUT_PREFIX] = "invalid_publish_topic"
            if not errors:
                if (
                    user_input[CONF_TOPIC_IN_PREFIX]
                    == user_input[CONF_TOPIC_OUT_PREFIX]
                ):
                    errors[CONF_TOPIC_OUT_PREFIX] = "same_topic"
                elif self._check_topic_exists(user_input[CONF_TOPIC_OUT_PREFIX]):
                    errors[CONF_TOPIC_OUT_PREFIX] = "duplicate_topic"

            errors.update(
                await self.validate_common(CONF_GATEWAY_TYPE_MQTT, errors, user_input)
            )
            if not errors:
                return self._async_create_entry(user_input)

        user_input = user_input or {}
        schema = _get_schema_common(user_input)
        schema[
            vol.Required(CONF_RETAIN, default=user_input.get(CONF_RETAIN, True))
        ] = bool
        schema[
            vol.Required(
                CONF_TOPIC_IN_PREFIX, default=user_input.get(CONF_TOPIC_IN_PREFIX, "")
            )
        ] = str
        schema[
            vol.Required(
                CONF_TOPIC_OUT_PREFIX, default=user_input.get(CONF_TOPIC_OUT_PREFIX, "")
            )
        ] = str

        schema = vol.Schema(schema)
        return self.async_show_form(
            step_id="gw_mqtt", data_schema=schema, errors=errors
        )

    @callback
    def _async_create_entry(
        self, user_input: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Create the config entry."""
        return self.async_create_entry(
            title=f"{user_input[CONF_DEVICE]}",
            data={**user_input, CONF_GATEWAY_TYPE: self._gw_type},
        )

    def _normalize_persistence_file(self, path: str) -> str:
        return os.path.realpath(os.path.normcase(self.hass.config.path(path)))

    async def validate_common(
        self,
        gw_type: ConfGatewayType,
        errors: dict[str, str],
        user_input: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Validate parameters common to all gateway types."""
        if user_input is not None:
            errors.update(_validate_version(user_input.get(CONF_VERSION)))

            if gw_type != CONF_GATEWAY_TYPE_MQTT:
                if gw_type == CONF_GATEWAY_TYPE_TCP:
                    verification_func = is_socket_address
                else:
                    verification_func = is_serial_port

                try:
                    await self.hass.async_add_executor_job(
                        verification_func, user_input.get(CONF_DEVICE)
                    )
                except vol.Invalid:
                    errors[CONF_DEVICE] = (
                        "invalid_ip"
                        if gw_type == CONF_GATEWAY_TYPE_TCP
                        else "invalid_serial"
                    )
            if CONF_PERSISTENCE_FILE in user_input:
                try:
                    is_persistence_file(user_input[CONF_PERSISTENCE_FILE])
                except vol.Invalid:
                    errors[CONF_PERSISTENCE_FILE] = "invalid_persistence_file"
                else:
                    real_persistence_path = self._normalize_persistence_file(
                        user_input[CONF_PERSISTENCE_FILE]
                    )
                    for other_entry in self.hass.config_entries.async_entries(DOMAIN):
                        if CONF_PERSISTENCE_FILE not in other_entry.data:
                            continue
                        if real_persistence_path == self._normalize_persistence_file(
                            other_entry.data[CONF_PERSISTENCE_FILE]
                        ):
                            errors[CONF_PERSISTENCE_FILE] = "duplicate_persistence_file"
                            break

            for other_entry in self.hass.config_entries.async_entries(DOMAIN):
                if _is_same_device(gw_type, user_input, other_entry):
                    errors["base"] = "already_configured"
                    break

            # if no errors so far, try to connect
            if not errors and not await try_connect(self.hass, user_input):
                errors["base"] = "cannot_connect"

        return errors
