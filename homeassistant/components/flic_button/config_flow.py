"""Config flow for Flic Button integration."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from bleak import BleakError
import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import (
    CONF_BATTERY_LEVEL,
    CONF_BUTTON_UUID,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_PUSH_TWIST_MODE,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DEVICE_TYPE_MODEL_NAMES,
    DOMAIN,
    FLIC_SERVICE_UUID,
    PAIRING_TIMEOUT,
    TWIST_SERVICE_UUID,
    DeviceType,
    PushTwistMode,
)
from .flic_client import FlicAuthenticationError, FlicClient, FlicPairingError

_LOGGER = logging.getLogger(__name__)


class FlicButtonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flic Button."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._client: FlicClient | None = None
        self._device_type: DeviceType = DeviceType.FLIC2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return FlicButtonOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated setup."""
        return self.async_abort(reason="use_bluetooth_discovery")

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info

        # Detect device type from service UUID
        service_uuids = [str(uuid).lower() for uuid in discovery_info.service_uuids]
        if TWIST_SERVICE_UUID.lower() in service_uuids:
            self._device_type = DeviceType.TWIST
        elif FLIC_SERVICE_UUID.lower() in service_uuids:
            # Flic 2/Duo use same service UUID - will be differentiated during pairing
            self._device_type = DeviceType.FLIC2
        else:
            self._device_type = DeviceType.FLIC2  # Default

        _LOGGER.debug(
            "Discovered Flic device %s with type %s (service_uuids=%s)",
            discovery_info.address,
            self._device_type.value,
            service_uuids,
        )

        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }

        return await self.async_step_pair()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle bluetooth confirmation step."""
        assert self._discovery_info is not None

        if user_input is None:
            name = self._discovery_info.name or self._discovery_info.address
            return self.async_show_form(
                step_id="bluetooth_confirm",
                description_placeholders={"name": name},
            )

        return await self.async_step_pair()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle pairing step."""
        assert self._discovery_info is not None

        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug(
                "Pairing form submitted for button %s (device_type=%s)",
                self._discovery_info.address,
                self._device_type.value,
            )
            # Create client with detected device type
            if not self._client:
                _LOGGER.debug(
                    "Creating FlicClient for device %s (type=%s)",
                    self._discovery_info.device,
                    self._device_type.value,
                )
                self._client = FlicClient(
                    address=self._discovery_info.device.address,
                    ble_device=self._discovery_info.device,
                    device_type=self._device_type,
                )

            try:
                # Connect to button
                await self._client.connect()

                # Perform full pairing
                (
                    pairing_id,
                    pairing_key,
                    serial_number,
                    battery_level,
                    sig_bits,
                    button_uuid,
                ) = await asyncio.wait_for(
                    self._client.full_verify_pairing(),
                    timeout=PAIRING_TIMEOUT,
                )

                # Disconnect after pairing
                await self._client.disconnect()

                # Use device type detected from service UUID (set in async_step_bluetooth)
                # Twist has a unique service UUID, so trust that detection.
                # For Flic 2 vs Duo (same service UUID), check serial prefix.
                final_device_type = (
                    DeviceType.TWIST
                    if self._device_type == DeviceType.TWIST
                    else DeviceType.from_serial_number(serial_number)
                )

                model_name = DEVICE_TYPE_MODEL_NAMES[final_device_type]

                title = f"{model_name} ({serial_number})"

                # Build config entry data
                entry_data: dict[str, Any] = {
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_PAIRING_ID: pairing_id,
                    CONF_PAIRING_KEY: pairing_key.hex(),
                    CONF_SERIAL_NUMBER: serial_number,
                    CONF_BATTERY_LEVEL: battery_level,
                    CONF_DEVICE_TYPE: final_device_type.value,
                    CONF_SIG_BITS: sig_bits,
                }

                # Store button UUID for Twist firmware updates
                if button_uuid is not None:
                    entry_data[CONF_BUTTON_UUID] = button_uuid.hex()

                # Create config entry
                return self.async_create_entry(
                    title=title,
                    data=entry_data,
                )

            except (TimeoutError, BleakError):
                _LOGGER.exception("Cannot connect to button")
                errors["base"] = "cannot_connect"
            except FlicPairingError:
                _LOGGER.exception("Pairing failed")
                errors["base"] = "pairing_failed"
            except FlicAuthenticationError:
                _LOGGER.exception("Authentication failed")
                errors["base"] = "invalid_signature"
            except Exception:
                _LOGGER.exception("Unexpected exception during pairing")
                errors["base"] = "unknown"
            finally:
                if self._client:
                    with contextlib.suppress(Exception):
                        await self._client.disconnect()

        # Show pairing form
        return self.async_show_form(
            step_id="pair",
            errors=errors,
            description_placeholders={
                "name": self._discovery_info.name or self._discovery_info.address
            },
        )


class FlicButtonOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Flic Button integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        # Only show options for Twist devices
        device_type = self.config_entry.data.get(CONF_DEVICE_TYPE)
        _LOGGER.debug(
            "Options flow init: device_type=%s, expected=%s",
            device_type,
            DeviceType.TWIST.value,
        )
        if device_type != DeviceType.TWIST.value:
            return self.async_abort(reason="not_twist_device")

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_mode = self.config_entry.options.get(
            CONF_PUSH_TWIST_MODE, PushTwistMode.DEFAULT
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PUSH_TWIST_MODE, default=current_mode): vol.In(
                        {
                            PushTwistMode.DEFAULT: "Default",
                            PushTwistMode.SELECTOR: "Selector mode",
                        }
                    ),
                }
            ),
        )
