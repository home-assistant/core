"""Config flow for Qingping integration."""

import asyncio
from typing import Any, Final, override

from qingping_ble import QingpingBluetoothDeviceData as DeviceData
from qingping_tlv import is_tlv_format
import voluptuous as vol

from homeassistant.components import bluetooth, mqtt
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
    async_process_advertisements,
)
from homeassistant.components.mqtt import async_wait_for_mqtt_client
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_MAC, CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CONNECTION_TYPE,
    CONNECTION_MQTT,
    DOMAIN,
    MODELS,
    MQTT_TOPIC_PREFIX,
)

# How long to wait for additional advertisement packets if we don't have the right ones
ADDITIONAL_DISCOVERY_TIMEOUT = 60

# How long to listen on MQTT for devices publishing realtime data
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


class QingpingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for qingping."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_device: DeviceData | None = None
        self._discovered_devices: dict[str, str] = {}

    async def _async_wait_for_full_advertisement(
        self, discovery_info: BluetoothServiceInfoBleak, device: DeviceData
    ) -> BluetoothServiceInfoBleak:
        """Wait for the full advertisement.

        Sometimes the first advertisement we receive is blank or incomplete.
        """
        if device.supported(discovery_info):
            return discovery_info
        return await async_process_advertisements(
            self.hass,
            device.supported,
            {"address": discovery_info.address},
            BluetoothScanningMode.ACTIVE,
            ADDITIONAL_DISCOVERY_TIMEOUT,
        )

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = DeviceData()
        try:
            self._discovery_info = await self._async_wait_for_full_advertisement(
                discovery_info, device
            )
        except TimeoutError:
            return self.async_abort(reason="not_supported")
        self._discovery_info = discovery_info
        self._discovered_device = device
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        device = self._discovered_device
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        title = device.title or device.get_device_name() or discovery_info.name
        if user_input is not None:
            return self.async_create_entry(title=title, data={})

        self._set_confirm_only()
        placeholders = {"name": title}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to choose how the device connects."""
        return self.async_show_menu(
            step_id="user", menu_options=["bluetooth_device", "mqtt_device"]
        )

    async def async_step_bluetooth_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick a discovered Bluetooth device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices[address], data={}
            )

        await bluetooth.async_request_active_scan(self.hass)
        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = DeviceData()
            if device.supported(discovery_info):
                self._discovered_devices[address] = (
                    device.title or device.get_device_name() or discovery_info.name
                )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="bluetooth_device",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )

    async def async_step_mqtt_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to set up an MQTT device."""
        if not await async_wait_for_mqtt_client(self.hass):
            return self.async_abort(reason="mqtt_not_configured")
        if user_input is not None:
            mac = _normalize_mac(user_input[CONF_MAC])
            if not _is_valid_mac(mac):
                return self.async_show_form(
                    step_id="mqtt_device",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_MAC): str,
                            vol.Required(CONF_MODEL): _model_selector(),
                        }
                    ),
                    errors={CONF_MAC: "invalid_mac"},
                )
            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured()
            model = user_input[CONF_MODEL]
            return self.async_create_entry(
                title=f"{MODELS[model]} ({mac})",
                data={
                    CONF_CONNECTION_TYPE: CONNECTION_MQTT,
                    CONF_MAC: mac,
                    CONF_MODEL: model,
                },
            )
        discovered = await self._async_discover_mqtt_devices()
        return self.async_show_form(
            step_id="mqtt_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAC): _mac_selector(discovered),
                    vol.Required(CONF_MODEL): _model_selector(),
                }
            ),
        )

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
