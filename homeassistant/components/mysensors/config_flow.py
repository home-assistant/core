"""Config flow for MySensors."""

from __future__ import annotations

import os
from typing import Any

from awesomeversion import (
    AwesomeVersion,
    AwesomeVersionStrategy,
    AwesomeVersionStrategyException,
)
import voluptuous as vol

from homeassistant.components.mqtt import (
    DOMAIN as MQTT_DOMAIN,
    valid_publish_topic,
    valid_subscribe_topic,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import VolDictType

from .const import (
    CONF_BAUD_RATE,
    CONF_GATEWAY_TYPE,
    CONF_GATEWAY_TYPE_MQTT,
    CONF_GATEWAY_TYPE_SERIAL,
    CONF_GATEWAY_TYPE_TCP,
    CONF_PERSISTENCE_FILE,
    CONF_RETAIN,
    CONF_TCP_PORT,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
    CONF_VERSION,
    DOMAIN,
    ConfGatewayType,
)
from .gateway import MQTT_COMPONENT, is_serial_port, is_socket_address, try_connect

DEFAULT_BAUD_RATE = 115200
DEFAULT_TCP_PORT = 5003
DEFAULT_VERSION = "1.4"

_PORT_SELECTOR = vol.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=65535, mode=selector.NumberSelectorMode.BOX
        ),
    ),
    vol.Coerce(int),
)


def is_persistence_file(value: str) -> str:
    """Validate that persistence file path ends in either .pickle or .json."""
    if value.endswith((".json", ".pickle")):
        return value
    raise vol.Invalid(f"{value} does not end in either `.json` or `.pickle`")


def _get_schema_common(user_input: dict[str, str]) -> dict:
    """Create a schema with options common to all gateway types."""
    return {
        vol.Required(
            CONF_VERSION,
            description={
                "suggested_value": user_input.get(CONF_VERSION, DEFAULT_VERSION)
            },
        ): str,
        vol.Optional(CONF_PERSISTENCE_FILE): str,
    }


def _validate_version(version: str) -> dict[str, str]:
    """Validate a version string from the user."""
    version_okay = True
    try:
        AwesomeVersion(
            version,
            ensure_strategy=[
                AwesomeVersionStrategy.SIMPLEVER,
                AwesomeVersionStrategy.SEMVER,
            ],
        )
    except AwesomeVersionStrategyException:
        version_okay = False

    if version_okay:
        return {}
    return {CONF_VERSION: "invalid_version"}


def _is_same_device(
    gw_type: ConfGatewayType, user_input: dict[str, Any], entry: ConfigEntry
) -> bool:
    """Check if another ConfigDevice is actually the same as user_input.

    This function only compares addresses and tcp ports, so it is possible to fool it with tricks like port forwarding.
    """
    if entry.data[CONF_DEVICE] != user_input[CONF_DEVICE]:
        return False
    if gw_type == CONF_GATEWAY_TYPE_TCP:
        entry_tcp_port: int = entry.data[CONF_TCP_PORT]
        input_tcp_port: int = user_input[CONF_TCP_PORT]
        return entry_tcp_port == input_tcp_port
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


class MySensorsConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    def __init__(self) -> None:
        """Set up config flow."""
        self._gw_type: str | None = None

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Create a config entry from frontend user input."""
        return await self.async_step_select_gateway_type()

    async def async_step_select_gateway_type(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the select gateway type menu."""
        return self.async_show_menu(
            step_id="select_gateway_type",
            menu_options=["gw_serial", "gw_tcp", "gw_mqtt"],
        )

    async def async_step_gw_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create config entry for a serial gateway."""
        gw_type = self._gw_type = CONF_GATEWAY_TYPE_SERIAL
        errors: dict[str, str] = {}

        if user_input is not None:
            errors.update(await self.validate_common(gw_type, errors, user_input))
            if not errors:
                return self._async_create_entry(user_input)

        user_input = user_input or {}
        schema: VolDictType = {
            vol.Required(
                CONF_DEVICE, default=user_input.get(CONF_DEVICE, "/dev/ttyACM0")
            ): str,
            vol.Required(
                CONF_BAUD_RATE,
                default=user_input.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE),
            ): cv.positive_int,
        }
        schema.update(_get_schema_common(user_input))

        return self.async_show_form(
            step_id="gw_serial", data_schema=vol.Schema(schema), errors=errors
        )

    async def async_step_gw_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a config entry for a tcp gateway."""
        gw_type = self._gw_type = CONF_GATEWAY_TYPE_TCP
        errors: dict[str, str] = {}

        if user_input is not None:
            errors.update(await self.validate_common(gw_type, errors, user_input))
            if not errors:
                return self._async_create_entry(user_input)

        user_input = user_input or {}
        schema: VolDictType = {
            vol.Required(
                CONF_DEVICE, default=user_input.get(CONF_DEVICE, "127.0.0.1")
            ): str,
            vol.Optional(
                CONF_TCP_PORT, default=user_input.get(CONF_TCP_PORT, DEFAULT_TCP_PORT)
            ): _PORT_SELECTOR,
        }
        schema.update(_get_schema_common(user_input))

        return self.async_show_form(
            step_id="gw_tcp", data_schema=vol.Schema(schema), errors=errors
        )

    def _check_topic_exists(self, topic: str) -> bool:
        for other_config in self._async_current_entries():
            if topic == other_config.data.get(
                CONF_TOPIC_IN_PREFIX
            ) or topic == other_config.data.get(CONF_TOPIC_OUT_PREFIX):
                return True
        return False

    async def async_step_gw_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a config entry for a mqtt gateway."""
        # Naive check that doesn't consider config entry state.
        if MQTT_DOMAIN not in self.hass.config.components:
            return self.async_abort(reason="mqtt_required")

        gw_type = self._gw_type = CONF_GATEWAY_TYPE_MQTT
        errors: dict[str, str] = {}

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

            errors.update(await self.validate_common(gw_type, errors, user_input))
            if not errors:
                return self._async_create_entry(user_input)

        user_input = user_input or {}
        schema: VolDictType = {
            vol.Required(
                CONF_TOPIC_IN_PREFIX, default=user_input.get(CONF_TOPIC_IN_PREFIX, "")
            ): str,
            vol.Required(
                CONF_TOPIC_OUT_PREFIX, default=user_input.get(CONF_TOPIC_OUT_PREFIX, "")
            ): str,
            vol.Required(CONF_RETAIN, default=user_input.get(CONF_RETAIN, True)): bool,
        }
        schema.update(_get_schema_common(user_input))

        return self.async_show_form(
            step_id="gw_mqtt", data_schema=vol.Schema(schema), errors=errors
        )

    @callback
    def _async_create_entry(self, user_input: dict[str, Any]) -> ConfigFlowResult:
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
        user_input: dict[str, Any],
    ) -> dict[str, str]:
        """Validate parameters common to all gateway types."""
        errors.update(_validate_version(user_input[CONF_VERSION]))

        if gw_type != CONF_GATEWAY_TYPE_MQTT:
            if gw_type == CONF_GATEWAY_TYPE_TCP:
                verification_func = is_socket_address
            else:
                verification_func = is_serial_port

            try:
                await self.hass.async_add_executor_job(
                    verification_func, user_input[CONF_DEVICE]
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
                real_persistence_path = user_input[CONF_PERSISTENCE_FILE] = (
                    self._normalize_persistence_file(user_input[CONF_PERSISTENCE_FILE])
                )
                for other_entry in self._async_current_entries():
                    if CONF_PERSISTENCE_FILE not in other_entry.data:
                        continue
                    if real_persistence_path == self._normalize_persistence_file(
                        other_entry.data[CONF_PERSISTENCE_FILE]
                    ):
                        errors[CONF_PERSISTENCE_FILE] = "duplicate_persistence_file"
                        break

        if not errors:
            for other_entry in self._async_current_entries():
                if _is_same_device(gw_type, user_input, other_entry):
                    errors["base"] = "already_configured"
                    break

        # if no errors so far, try to connect
        if not errors and not await try_connect(self.hass, gw_type, user_input):
            errors["base"] = "cannot_connect"

        return errors
