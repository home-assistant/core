"""Config flow for MQTT."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
import queue
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.const import (
    CONF_DISCOVERY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.typing import ConfigType

from .client import MqttClientSetup
from .const import (
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_WILL_MESSAGE,
    DEFAULT_BIRTH,
    DEFAULT_DISCOVERY,
    DEFAULT_PORT,
    DEFAULT_WILL,
    DOMAIN,
)
from .util import MQTT_WILL_BIRTH_SCHEMA, get_mqtt_data

MQTT_TIMEOUT = 5

BOOLEAN_SELECTOR = BooleanSelector()
TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
PUBLISH_TOPIC_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
PORT_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)),
    vol.Coerce(int),
)
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
QOS_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=0, max=2)),
    vol.Coerce(int),
)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    _hassio_discovery = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MQTTOptionsFlowHandler:
        """Get the options flow for this handler."""
        return MQTTOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_broker()

    async def async_step_broker(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm the setup."""
        yaml_config: ConfigType = get_mqtt_data(self.hass, True).config or {}
        errors: dict[str, str] = {}
        fields: OrderedDict[Any, Any] = OrderedDict()
        validated_user_input: dict[str, Any] = {}
        if await async_get_broker_settings(
            self.hass,
            fields,
            yaml_config,
            None,
            user_input,
            validated_user_input,
            errors,
        ):
            test_config: dict[str, Any] = yaml_config.copy()
            test_config.update(validated_user_input)
            can_connect = await self.hass.async_add_executor_job(
                try_connection,
                test_config,
            )

            if can_connect:
                validated_user_input[CONF_DISCOVERY] = DEFAULT_DISCOVERY
                return self.async_create_entry(
                    title=validated_user_input[CONF_BROKER],
                    data=validated_user_input,
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="broker", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> FlowResult:
        """Receive a Hass.io discovery."""
        await self._async_handle_discovery_without_unique_id()

        self._hassio_discovery = discovery_info.config

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm a Hass.io discovery."""
        errors: dict[str, str] = {}
        assert self._hassio_discovery

        if user_input is not None:
            data: dict[str, Any] = self._hassio_discovery.copy()
            data[CONF_BROKER] = data.pop(CONF_HOST)
            can_connect = await self.hass.async_add_executor_job(
                try_connection,
                data,
            )

            if can_connect:
                return self.async_create_entry(
                    title=data["addon"],
                    data={
                        CONF_BROKER: data[CONF_BROKER],
                        CONF_PORT: data[CONF_PORT],
                        CONF_USERNAME: data.get(CONF_USERNAME),
                        CONF_PASSWORD: data.get(CONF_PASSWORD),
                        CONF_DISCOVERY: DEFAULT_DISCOVERY,
                    },
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
            errors=errors,
        )


class MQTTOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle MQTT options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize MQTT options flow."""
        self.config_entry = config_entry
        self.broker_config: dict[str, str | int] = {}
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input: None = None) -> FlowResult:
        """Manage the MQTT options."""
        return await self.async_step_broker()

    async def async_step_broker(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the MQTT broker configuration."""
        errors: dict[str, str] = {}
        yaml_config: ConfigType = get_mqtt_data(self.hass, True).config or {}
        fields: OrderedDict[Any, Any] = OrderedDict()
        validated_user_input: dict[str, Any] = {}
        if await async_get_broker_settings(
            self.hass,
            fields,
            yaml_config,
            self.config_entry.data,
            user_input,
            validated_user_input,
            errors,
        ):
            test_config: dict[str, Any] = yaml_config.copy()
            test_config.update(validated_user_input)
            can_connect = await self.hass.async_add_executor_job(
                try_connection,
                test_config,
            )

            if can_connect:
                self.broker_config.update(validated_user_input)
                return await self.async_step_options()

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="broker",
            data_schema=vol.Schema(fields),
            errors=errors,
            last_step=False,
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the MQTT options."""
        errors = {}
        current_config = self.config_entry.data
        yaml_config = get_mqtt_data(self.hass, True).config or {}
        options_config: dict[str, Any] = {}
        bad_input: bool = False

        def _birth_will(birt_or_will: str) -> dict:
            """Return the user input for birth or will."""
            assert user_input
            return {
                ATTR_TOPIC: user_input[f"{birt_or_will}_topic"],
                ATTR_PAYLOAD: user_input.get(f"{birt_or_will}_payload", ""),
                ATTR_QOS: user_input[f"{birt_or_will}_qos"],
                ATTR_RETAIN: user_input[f"{birt_or_will}_retain"],
            }

        def _validate(
            field: str, values: dict[str, Any], error_code: str, schema: Callable
        ):
            """Validate the user input."""
            nonlocal bad_input
            try:
                option_values = schema(values)
                options_config[field] = option_values
            except vol.Invalid:
                errors["base"] = error_code
                bad_input = True

        if user_input is not None:
            # validate input
            options_config[CONF_DISCOVERY] = user_input[CONF_DISCOVERY]
            if "birth_topic" in user_input:
                _validate(
                    CONF_BIRTH_MESSAGE,
                    _birth_will("birth"),
                    "bad_birth",
                    MQTT_WILL_BIRTH_SCHEMA,
                )
            if not user_input["birth_enable"]:
                options_config[CONF_BIRTH_MESSAGE] = {}

            if "will_topic" in user_input:
                _validate(
                    CONF_WILL_MESSAGE,
                    _birth_will("will"),
                    "bad_will",
                    MQTT_WILL_BIRTH_SCHEMA,
                )
            if not user_input["will_enable"]:
                options_config[CONF_WILL_MESSAGE] = {}

            if not bad_input:
                updated_config = {}
                updated_config.update(self.broker_config)
                updated_config.update(options_config)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=updated_config,
                    title=str(self.broker_config[CONF_BROKER]),
                )
                return self.async_create_entry(title="", data={})

        birth = {
            **DEFAULT_BIRTH,
            **current_config.get(
                CONF_BIRTH_MESSAGE, yaml_config.get(CONF_BIRTH_MESSAGE, {})
            ),
        }
        will = {
            **DEFAULT_WILL,
            **current_config.get(
                CONF_WILL_MESSAGE, yaml_config.get(CONF_WILL_MESSAGE, {})
            ),
        }
        discovery = current_config.get(
            CONF_DISCOVERY, yaml_config.get(CONF_DISCOVERY, DEFAULT_DISCOVERY)
        )

        # build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Optional(CONF_DISCOVERY, default=discovery)] = BOOLEAN_SELECTOR

        # Birth message is disabled if CONF_BIRTH_MESSAGE = {}
        fields[
            vol.Optional(
                "birth_enable",
                default=CONF_BIRTH_MESSAGE not in current_config
                or current_config[CONF_BIRTH_MESSAGE] != {},
            )
        ] = BOOLEAN_SELECTOR
        fields[
            vol.Optional(
                "birth_topic", description={"suggested_value": birth[ATTR_TOPIC]}
            )
        ] = PUBLISH_TOPIC_SELECTOR
        fields[
            vol.Optional(
                "birth_payload", description={"suggested_value": birth[CONF_PAYLOAD]}
            )
        ] = TEXT_SELECTOR
        fields[vol.Optional("birth_qos", default=birth[ATTR_QOS])] = QOS_SELECTOR
        fields[
            vol.Optional("birth_retain", default=birth[ATTR_RETAIN])
        ] = BOOLEAN_SELECTOR

        # Will message is disabled if CONF_WILL_MESSAGE = {}
        fields[
            vol.Optional(
                "will_enable",
                default=CONF_WILL_MESSAGE not in current_config
                or current_config[CONF_WILL_MESSAGE] != {},
            )
        ] = BOOLEAN_SELECTOR
        fields[
            vol.Optional(
                "will_topic", description={"suggested_value": will[ATTR_TOPIC]}
            )
        ] = PUBLISH_TOPIC_SELECTOR
        fields[
            vol.Optional(
                "will_payload", description={"suggested_value": will[CONF_PAYLOAD]}
            )
        ] = TEXT_SELECTOR
        fields[vol.Optional("will_qos", default=will[ATTR_QOS])] = QOS_SELECTOR
        fields[
            vol.Optional("will_retain", default=will[ATTR_RETAIN])
        ] = BOOLEAN_SELECTOR

        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema(fields),
            errors=errors,
            last_step=True,
        )


async def async_get_broker_settings(
    hass: HomeAssistant,
    fields: OrderedDict[Any, Any],
    yaml_config: ConfigType,
    entry_config: MappingProxyType[str, Any] | None,
    user_input: dict[str, Any] | None,
    validated_user_input: dict[str, Any],
    errors: dict[str, str],
) -> bool:
    """Build the config flow schema to collect the broker settings.

    Returns True when settings are collected successfully.
    """
    user_input_basic: dict[str, Any] = {}
    current_config = entry_config.copy() if entry_config is not None else {}

    if user_input is not None:
        validated_user_input.update(user_input)
        return True

    # Update the current settings the the new posted data to fill the defaults
    current_config.update(user_input_basic)

    # Get default settings (if any)
    current_broker = current_config.get(CONF_BROKER, yaml_config.get(CONF_BROKER))
    current_port = current_config.get(
        CONF_PORT, yaml_config.get(CONF_PORT, DEFAULT_PORT)
    )
    current_user = current_config.get(CONF_USERNAME, yaml_config.get(CONF_USERNAME))
    current_pass = current_config.get(CONF_PASSWORD, yaml_config.get(CONF_PASSWORD))

    # Build form
    fields[vol.Required(CONF_BROKER, default=current_broker)] = TEXT_SELECTOR
    fields[vol.Required(CONF_PORT, default=current_port)] = PORT_SELECTOR
    fields[
        vol.Optional(
            CONF_USERNAME,
            description={"suggested_value": current_user},
        )
    ] = TEXT_SELECTOR
    fields[
        vol.Optional(
            CONF_PASSWORD,
            description={"suggested_value": current_pass},
        )
    ] = PASSWORD_SELECTOR

    # Show form
    return False


def try_connection(
    user_input: dict[str, Any],
) -> bool:
    """Test if we can connect to an MQTT broker."""
    # We don't import on the top because some integrations
    # should be able to optionally rely on MQTT.
    import paho.mqtt.client as mqtt  # pylint: disable=import-outside-toplevel

    client = MqttClientSetup(user_input).client

    result: queue.Queue[bool] = queue.Queue(maxsize=1)

    def on_connect(client_, userdata, flags, result_code):
        """Handle connection result."""
        result.put(result_code == mqtt.CONNACK_ACCEPTED)

    client.on_connect = on_connect

    client.connect_async(user_input[CONF_BROKER], user_input[CONF_PORT])
    client.loop_start()

    try:
        return result.get(timeout=MQTT_TIMEOUT)
    except queue.Empty:
        return False
    finally:
        client.disconnect()
        client.loop_stop()
