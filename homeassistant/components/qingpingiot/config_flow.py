"""Config flow for Qingping IoT integration."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_DEVICE, CONF_MAC, CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, MODEL_OPTIONS, MQTT_TOPIC_PREFIX

_LOGGER = logging.getLogger(__name__)

MANUAL_ENTRY_STRING = "manual"


def _clean_mac(mac: str) -> str:
    """Normalize MAC address by removing colons and uppercasing."""
    return mac.replace(":", "").upper()


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    """Represent a discovered Qingping device via MQTT."""

    name: str
    mac: str
    model: str


class QingpingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qingping IoT."""

    VERSION = 1
    MINOR_VERSION = 1

    _discovered_devices: dict[str, DiscoveredDevice] = {}
    _selected_device: DiscoveredDevice | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: show discovered devices or manual entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input[CONF_DEVICE]

            if selected == MANUAL_ENTRY_STRING:
                return await self.async_step_manual()

            self._selected_device = self._discovered_devices[selected]
            await self.async_set_unique_id(self._selected_device.mac)
            self._abort_if_unique_id_configured()

            return await self.async_step_confirm()

        await self._async_discover_devices()

        if not self._discovered_devices:
            return await self.async_step_manual()

        device_options: list[SelectOptionDict] = [
            SelectOptionDict(label=device.name, value=mac)
            for mac, device in self._discovered_devices.items()
        ]
        device_options.append(
            SelectOptionDict(
                label="Manually add a device",
                value=MANUAL_ENTRY_STRING,
            )
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): SelectSelector(
                        SelectSelectorConfig(
                            options=device_options,
                            mode=SelectSelectorMode.LIST,
                            translation_key="device",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovered device and select model."""
        assert self._selected_device is not None
        device = self._selected_device
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=device.mac,
                data={
                    CONF_MAC: device.mac,
                    CONF_MODEL: user_input.get(CONF_MODEL),
                },
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=MODEL_OPTIONS,
                            mode=SelectSelectorMode.LIST,
                            translation_key="model",
                        )
                    ),
                }
            ),
            description_placeholders={"mac": device.mac},
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual device configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = _clean_mac(user_input[CONF_MAC])

            if not self._is_valid_mac(mac):
                errors["base"] = "invalid_mac"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=mac,
                    data={
                        CONF_MAC: mac,
                        CONF_MODEL: user_input.get(CONF_MODEL),
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAC): str,
                    vol.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=MODEL_OPTIONS,
                            mode=SelectSelectorMode.LIST,
                            translation_key="model",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-configuration of a device."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        current_model = reconfigure_entry.data.get(CONF_MODEL)

        if user_input is not None:
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data_updates={CONF_MODEL: user_input[CONF_MODEL]},
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL, default=current_model): SelectSelector(
                        SelectSelectorConfig(
                            options=MODEL_OPTIONS,
                            mode=SelectSelectorMode.LIST,
                            translation_key="model",
                        )
                    ),
                }
            ),
            description_placeholders={
                "device_name": reconfigure_entry.title,
            },
            errors=errors,
        )

    async def _async_discover_devices(self) -> None:
        """Discover Qingping devices via MQTT."""
        self._discovered_devices = {}
        configured_macs = {entry.unique_id for entry in self._async_current_entries()}

        try:
            if not await mqtt.async_wait_for_mqtt_client(self.hass):
                _LOGGER.debug("MQTT client not available")
                return
        except ConnectionError:
            _LOGGER.debug("MQTT not available")
            return

        discovered: dict[str, DiscoveredDevice] = {}

        def _handle_message(msg: mqtt.ReceiveMessage) -> None:
            """Handle a received MQTT message for device discovery."""
            try:
                topic_parts = msg.topic.split("/")
                if len(topic_parts) < 2:
                    return

                raw_mac = topic_parts[-2]
                mac = _clean_mac(raw_mac)

                if not mac or mac in configured_macs or mac in discovered:
                    return

                name = f"Qingping ({raw_mac})"
                discovered[mac] = DiscoveredDevice(name=name, mac=mac, model="Unknown")
                _LOGGER.debug("Discovered device: %s (%s)", name, mac)

            except (ValueError, KeyError):
                _LOGGER.debug("Error parsing MQTT discovery message", exc_info=True)

        unsub = await mqtt.async_subscribe(
            self.hass,
            f"{MQTT_TOPIC_PREFIX}/#",
            _handle_message,
            1,
            encoding=None,
        )

        try:
            await asyncio.sleep(10)
        finally:
            unsub()

        self._discovered_devices = discovered
        _LOGGER.debug("Discovered %d Qingping device(s)", len(discovered))

    @staticmethod
    def _is_valid_mac(mac: str) -> bool:
        """Validate MAC address format (12 hex characters)."""
        if len(mac) != 12:
            return False
        try:
            int(mac, 16)
        except ValueError:
            return False
        else:
            return True

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> QingpingOptionsFlow:
        """Get the options flow for this handler."""
        return QingpingOptionsFlow()


class QingpingOptionsFlow(OptionsFlowWithReload):
    """Handle options flow for Qingping IoT."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_model = self.config_entry.data.get(CONF_MODEL)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL, default=current_model): SelectSelector(
                        SelectSelectorConfig(
                            options=MODEL_OPTIONS,
                            mode=SelectSelectorMode.LIST,
                            translation_key="model",
                        )
                    ),
                }
            ),
        )
