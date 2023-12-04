"""Config flow for drop_connect integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from .const import (
    CONF_COMMAND_TOPIC,
    CONF_DATA_TOPIC,
    CONF_DEVICE_DESC,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_HUB_ID,
    DISCOVERY_TOPIC,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

KEY_DEVICE_TYPE = "devType"
KEY_DEVICE_DESCRIPTION = "devDesc"
KEY_DEVICE_NAME = "name"


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle DROP config flow."""

    VERSION = 1

    _discovered_device_info: dict[str, Any] = {}
    _topic = DISCOVERY_TOPIC
    __command_topic: str | None = None
    __data_topic: str | None = None
    __device_desc: str | None = None
    __device_id: str | None = None
    __device_type: str | None = None
    __hub_id: str | None = None
    __name: str = ""

    async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> FlowResult:
        """Handle a flow initialized by MQTT discovery."""

        # Abort if the topic does not match our discovery topic or the payload is empty.
        if (
            discovery_info.subscribed_topic != DISCOVERY_TOPIC
            or not discovery_info.payload
        ):
            return self.async_abort(reason="invalid_discovery_info")

        payload_data = {}
        try:
            json_dict = (
                json_loads(discovery_info.payload)
                if isinstance(discovery_info.payload, str)
                else None
            )
            if isinstance(json_dict, dict):
                for k, v in json_dict.items():
                    if isinstance(k, str) and isinstance(v, str):
                        payload_data[k] = v
        except JSON_DECODE_EXCEPTIONS:
            _LOGGER.error(
                "Invalid MQTT discovery payload on %s: %s",
                discovery_info.topic,
                discovery_info.payload,
            )
            return self.async_abort(reason="invalid_discovery_info")

        # Extract the DROP hub ID and DROP device ID from the MQTT topic.
        topic_elements = discovery_info.topic.split("/")
        if not (
            topic_elements[2].startswith("DROP-") and topic_elements[3].isnumeric()
        ):
            return self.async_abort(reason="invalid_discovery_info")
        self.__hub_id = topic_elements[2]
        self.__device_id = topic_elements[3]

        existing_entry = await self.async_set_unique_id(
            f"{self.__hub_id}_{self.__device_id}"
        )
        if existing_entry is not None:
            # Note: returning "invalid_discovery_info" here instead of "already_configured"
            # allows discovery of additional device types.
            return self.async_abort(reason="invalid_discovery_info")

        # Discovery data must include the DROP device type and name.
        if (
            KEY_DEVICE_TYPE in payload_data
            and KEY_DEVICE_DESCRIPTION in payload_data
            and KEY_DEVICE_NAME in payload_data
        ):
            self.__device_type = payload_data[KEY_DEVICE_TYPE]
            self.__device_desc = payload_data[KEY_DEVICE_DESCRIPTION]
            self.__name = payload_data[KEY_DEVICE_NAME]
        else:
            _LOGGER.error(
                "Incomplete MQTT discovery payload on %s: %s",
                discovery_info.topic,
                discovery_info.payload,
            )
            return self.async_abort(reason="invalid_discovery_info")

        _LOGGER.debug(
            "MQTT discovery on %s: %s", discovery_info.topic, discovery_info.payload
        )

        # Define the data and command MQTT topics that will be used when this device is initialized.
        self.__data_topic = f"{DOMAIN}/{self.__hub_id}/data/{self.__device_id}/#"
        self.__command_topic = f"{DOMAIN}/{self.__hub_id}/cmd/{self.__device_id}"

        # Expose the device name to the 'Discovered' card
        self.context.update({"title_placeholders": {"name": self.__name}})

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm the setup."""
        if user_input is not None:
            device_data = {
                CONF_COMMAND_TOPIC: self.__command_topic,
                CONF_DATA_TOPIC: self.__data_topic,
                CONF_DEVICE_DESC: self.__device_desc,
                CONF_DEVICE_ID: self.__device_id,
                CONF_DEVICE_NAME: self.__name,
                CONF_DEVICE_TYPE: self.__device_type,
                CONF_HUB_ID: self.__hub_id,
            }
            return self.async_create_entry(title=self.__name, data=device_data)

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "device_name": self.__name,
                "device_type": self.__device_desc,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return self.async_abort(reason="not_supported")
