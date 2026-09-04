"""Config flow for the qingping_mqtt integration."""

import asyncio
from typing import Any, Final, override

from qingping_tlv import is_tlv_format
import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.mqtt import async_wait_for_mqtt_client
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MAC, CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, MODELS, MQTT_TOPIC_PREFIX

# How long to listen for devices publishing realtime data before showing the form
MQTT_DISCOVERY_TIMEOUT = 5

MODEL_OPTIONS: Final[list[SelectOptionDict]] = [
    SelectOptionDict(value=model, label=label) for model, label in MODELS.items()
]


def _model_selector() -> SelectSelector:
    """Return the model selector."""
    return SelectSelector(
        SelectSelectorConfig(
            options=MODEL_OPTIONS,
            mode=SelectSelectorMode.LIST,
            translation_key="model",
        )
    )


def _mac_selector(discovered: list[str]) -> SelectSelector:
    """Return a selector offering discovered devices with manual entry."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=mac, label=mac) for mac in discovered],
            mode=SelectSelectorMode.DROPDOWN,
            custom_value=True,
        )
    )


def _normalize_mac(mac: str) -> str:
    """Normalize a MAC address to 12 upper case hex characters."""
    return mac.replace(":", "").replace("-", "").strip().upper()


def _is_valid_mac(mac: str) -> bool:
    """Return True if the MAC address is 12 hex characters."""
    if len(mac) != 12:
        return False
    try:
        int(mac, 16)
    except ValueError:
        return False
    return True


class QingpingMqttConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for qingping_mqtt."""

    VERSION = 1

    _discovered_macs: list[str]

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to set up an MQTT device."""
        if not await async_wait_for_mqtt_client(self.hass):
            return self.async_abort(reason="mqtt_not_configured")
        if user_input is None:
            self._discovered_macs = await self._async_discover_mqtt_devices()
        data_schema = vol.Schema(
            {
                vol.Required(CONF_MAC): _mac_selector(self._discovered_macs),
                vol.Required(CONF_MODEL): _model_selector(),
            }
        )
        if user_input is not None:
            mac = _normalize_mac(user_input[CONF_MAC])
            if not _is_valid_mac(mac):
                return self.async_show_form(
                    step_id="user",
                    data_schema=data_schema,
                    errors={CONF_MAC: "invalid_mac"},
                )
            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured()
            model = user_input[CONF_MODEL]
            return self.async_create_entry(
                title=f"{MODELS[model]} ({mac})",
                data={CONF_MAC: mac, CONF_MODEL: model},
            )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def _async_discover_mqtt_devices(self) -> list[str]:
        """Listen for devices currently publishing realtime data on MQTT."""
        discovered: list[str] = []
        configured = self._async_current_ids()

        @callback
        def _handle_message(msg: mqtt.ReceiveMessage) -> None:
            """Register a device publishing on a qingping/<mac>/up topic."""
            topic_parts = msg.topic.split("/")
            if (
                len(topic_parts) != 3
                or topic_parts[0] != MQTT_TOPIC_PREFIX
                or topic_parts[2] != "up"
            ):
                return
            mac = _normalize_mac(topic_parts[1])
            if not _is_valid_mac(mac) or mac in configured or mac in discovered:
                return
            payload = msg.payload
            if isinstance(payload, str):
                payload = payload.encode()
            elif isinstance(payload, bytearray):
                payload = bytes(payload)
            if is_tlv_format(payload):
                discovered.append(mac)

        unsub = await mqtt.async_subscribe(
            self.hass,
            f"{MQTT_TOPIC_PREFIX}/#",
            _handle_message,
            encoding=None,
        )
        try:
            await asyncio.sleep(MQTT_DISCOVERY_TIMEOUT)
        finally:
            unsub()
        return discovered
