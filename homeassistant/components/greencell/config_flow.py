"""Config flow for Greencell EVSE integration in Home Assistant."""

import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any

from greencell_client.utils import GreencellUtils
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from . import const
from .const import (
    DOMAIN,
    GREENCELL_BROADCAST_TOPIC,
    GREENCELL_DISC_TOPIC,
    GREENCELL_HABU_DEN,
    GREENCELL_OTHER_DEVICE,
)

_LOGGER = logging.getLogger(__name__)


class EVSEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Greencell EVSE devices."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered: dict[str, dict[str, Any]] = {}
        self._discovered_serial: str | None = None
        self._discovery_event: asyncio.Event | None = None
        self._remove_listener: Callable | None = None

    def _get_device_name(self, serial: str) -> str:
        """Determine the device name based on the serial number."""
        return (
            GREENCELL_HABU_DEN
            if GreencellUtils.device_is_habu_den(serial)
            else GREENCELL_OTHER_DEVICE
        )

    @callback
    def _async_mqtt_message_received(self, msg: ReceiveMessage) -> None:
        """Handle incoming MQTT messages on the discovery topic."""
        try:
            payload = json.loads(msg.payload)
            serial = payload.get("id")
            if isinstance(serial, str) and serial.strip():
                self._discovered[serial] = payload
                if self._discovery_event:
                    self._discovery_event.set()
        except json.JSONDecodeError:
            _LOGGER.debug("Invalid JSON in discovery payload: %s", msg.payload)

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by MQTT discovery."""
        try:
            payload = json.loads(discovery_info.payload)
            serial = payload.get("id")
        except json.JSONDecodeError, AttributeError:
            return self.async_abort(reason="invalid_discovery_data")

        if not isinstance(serial, str) or not serial.strip():
            return self.async_abort(reason="invalid_discovery_data")

        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        if self._async_in_progress():
            return self.async_abort(reason="already_in_progress")

        self._discovered_serial = serial
        device_name = self._get_device_name(serial)
        self.context.update({"title_placeholders": {"name": f"{device_name} {serial}"}})

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm addition of a discovered device."""
        assert self._discovered_serial is not None
        serial = self._discovered_serial
        if user_input is not None:
            return self.async_create_entry(
                title=f"{self._get_device_name(serial)} {serial}",
                data={"serial_number": serial},
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"serial": serial},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manual step: start active discovery process."""
        try:
            if not mqtt.is_connected(self.hass):
                return self.async_abort(reason="mqtt_not_connected")
        except KeyError:
            return self.async_abort(reason="mqtt_not_configured")

        return await self.async_step_discover()

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Discovery step: subscribe, broadcast, and wait for responses."""
        self._discovery_event = asyncio.Event()

        try:
            self._remove_listener = await mqtt.async_subscribe(
                self.hass,
                GREENCELL_DISC_TOPIC,
                self._async_mqtt_message_received,
            )
        except HomeAssistantError, ValueError:
            return self.async_abort(reason="mqtt_subscription_failed")

        try:
            payload = json.dumps({"name": "BROADCAST"})
            await mqtt.async_publish(
                self.hass, GREENCELL_BROADCAST_TOPIC, payload, qos=0, retain=True
            )

            try:
                await asyncio.wait_for(
                    self._discovery_event.wait(), timeout=const.DISCOVERY_TIMEOUT
                )
                # Grace period for additional devices
                await asyncio.sleep(0.5)
            except TimeoutError:
                pass
        finally:
            self._remove_listener()

        if not self._discovered:
            return self.async_abort(reason="no_discovery_data")

        if len(self._discovered) == 1:
            serial = next(iter(self._discovered))
            return await self._async_create_entry(serial)

        return await self.async_step_select()

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user select one of the discovered devices."""
        if user_input is not None:
            serial = user_input["serial_number"]
            return await self._async_create_entry(serial)

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {vol.Required("serial_number"): vol.In(list(self._discovered.keys()))}
            ),
            description_placeholders={"count": str(len(self._discovered))},
        )

    async def _async_create_entry(self, serial: str) -> config_entries.ConfigFlowResult:
        """Finalize entry creation for selected device."""
        await self.async_set_unique_id(serial, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        device_name = self._get_device_name(serial)
        title = f"{device_name} {serial}"

        _LOGGER.info("Discovered and added device: %s", title)

        return self.async_create_entry(
            title=title,
            data={"serial_number": serial},
        )
