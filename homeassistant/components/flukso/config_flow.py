"""Config flow for Flukso."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_DEVICE_FIRMWARE, CONF_DEVICE_HASH, CONF_DEVICE_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        pass

    async def async_step_mqtt(self, discovery_info: DiscoveryInfoType) -> FlowResult:
        """Handle a flow initialized by MQTT discovery."""
        if not discovery_info["payload"]:
            return self.async_abort(reason="invalid_discovery_info")

        if not discovery_info["subscribed_topic"] == "/device/+/test/tap":
            return self.async_abort(reason="invalid_discovery_info")

        data = {}

        splitted_topic = discovery_info["topic"].split("/")
        data[CONF_DEVICE_HASH] = splitted_topic[2]
        data[CONF_DEVICE_SERIAL] = re.findall(
            "# serial: (.*)", discovery_info["payload"]
        )[0]
        data[CONF_DEVICE_FIRMWARE] = re.findall(
            "# firmware: (.*)", discovery_info["payload"]
        )[0]

        unique_id = (
            DOMAIN + "_" + data[CONF_DEVICE_HASH] + "_" + data[CONF_DEVICE_SERIAL]
        )

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        _LOGGER.info(
            f"Discovered new flukso {data[CONF_DEVICE_SERIAL]} ({data[CONF_DEVICE_HASH]}) with firmware {data[CONF_DEVICE_FIRMWARE]}"
        )

        return self.async_create_entry(
            title=f"Flukso {data[CONF_DEVICE_SERIAL]}", data=data
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        data = {}

        if user_input is not None:
            data[CONF_DEVICE_HASH] = user_input[CONF_DEVICE_HASH]
            data[CONF_DEVICE_SERIAL] = user_input[CONF_DEVICE_SERIAL]
            data[CONF_DEVICE_FIRMWARE] = user_input.get(CONF_DEVICE_FIRMWARE, "unknown")

            unique_id = (
                DOMAIN + "_" + data[CONF_DEVICE_HASH] + "_" + data[CONF_DEVICE_SERIAL]
            )

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            _LOGGER.info(
                f"Manually adding new flukso {data[CONF_DEVICE_SERIAL]} ({data[CONF_DEVICE_HASH]}) with firmware {data[CONF_DEVICE_FIRMWARE]}"
            )

            return self.async_create_entry(
                title=f"Flukso {data[CONF_DEVICE_SERIAL]}", data=data
            )

        fields = {}
        fields[vol.Required(CONF_DEVICE_HASH)] = str
        fields[vol.Required(CONF_DEVICE_SERIAL)] = str
        fields[vol.Optional(CONF_DEVICE_FIRMWARE)] = str

        return self.async_show_form(step_id="user", data_schema=vol.Schema(fields))
