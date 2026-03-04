"""Config flow for Flic Button integration."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from bleak import BleakError
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
    async_process_advertisements,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

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
        self._discovery_task: asyncio.Task[BluetoothServiceInfoBleak] | None = None
        self._pairing_started: bool = False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return FlicButtonOptionsFlowHandler()

    def _is_unconfigured_flic_device(
        self, service_info: BluetoothServiceInfoBleak
    ) -> bool:
        """Check if a discovered BLE device is a Flic button not yet configured."""
        service_uuids = [str(uuid).lower() for uuid in service_info.service_uuids]
        if (
            FLIC_SERVICE_UUID.lower() not in service_uuids
            and TWIST_SERVICE_UUID.lower() not in service_uuids
        ):
            return False
        return service_info.address not in self._async_current_ids(include_ignore=False)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated setup."""
        # If a discovery task is running or finished, handle it first
        if self._discovery_task:
            if not self._discovery_task.done():
                return self.async_show_progress(
                    step_id="user",
                    progress_action="wait_for_discovery",
                    progress_task=self._discovery_task,
                )

            try:
                self._discovery_info = self._discovery_task.result()
            except TimeoutError:
                self._discovery_task = None
                return self.async_abort(reason="no_devices_found")
            finally:
                self._discovery_task = None

            return self.async_show_progress_done(next_step_id="discovery_done")

        # Check if a Flic device is already visible
        for info in async_discovered_service_info(self.hass):
            if self._is_unconfigured_flic_device(info):
                self._discovery_info = info
                break

        # Already found a device — go straight to pairing
        if self._discovery_info is not None:
            return await self._async_set_device_and_pair(
                self._discovery_info, start_pairing=True
            )

        # No device yet — start waiting for one to appear
        self._discovery_task = self.hass.async_create_task(
            self._async_wait_for_flic_device(), eager_start=False
        )

        return self.async_show_progress(
            step_id="user",
            progress_action="wait_for_discovery",
            progress_task=self._discovery_task,
        )

    async def async_step_discovery_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle transition after discovery progress completes."""
        if self._discovery_info is None:
            return self.async_abort(reason="no_devices_found")
        return await self._async_set_device_and_pair(
            self._discovery_info, start_pairing=True
        )

    async def _async_wait_for_flic_device(self) -> BluetoothServiceInfoBleak:
        """Wait for a Flic device to appear via Bluetooth advertisements."""
        return await async_process_advertisements(
            self.hass,
            self._is_unconfigured_flic_device,
            {"connectable": True},
            BluetoothScanningMode.ACTIVE,
            PAIRING_TIMEOUT,
        )

    async def _async_set_device_and_pair(
        self,
        info: BluetoothServiceInfoBleak,
        *,
        start_pairing: bool = False,
    ) -> ConfigFlowResult:
        """Set discovery info from a found device and proceed to pairing."""
        self._discovery_info = info
        service_uuids = [str(uuid).lower() for uuid in info.service_uuids]

        if TWIST_SERVICE_UUID.lower() in service_uuids:
            self._device_type = DeviceType.TWIST
        else:
            self._device_type = DeviceType.FLIC2

        await self.async_set_unique_id(info.address, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": info.name or info.address}

        # When start_pairing is True, skip showing the form and pair immediately
        return await self.async_step_pair({} if start_pairing else None)

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        service_uuids = [str(uuid).lower() for uuid in discovery_info.service_uuids]

        if TWIST_SERVICE_UUID.lower() in service_uuids:
            self._device_type = DeviceType.TWIST
        else:
            self._device_type = DeviceType.FLIC2

        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle bluetooth confirmation step."""
        if self._discovery_info is None:
            return self.async_abort(reason="no_devices_found")

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
        if self._discovery_info is None:
            return self.async_abort(reason="no_devices_found")

        errors: dict[str, str] = {}

        if user_input is not None:
            # Guard against duplicate form submissions — the flag is set
            # synchronously before the first await to prevent races.
            if self._pairing_started:
                _LOGGER.debug("Ignoring duplicate pair submission")
                # Never create the entry here — the firmware check/update
                # chain will handle it. Just show the pair form as a no-op.
                return self.async_show_form(
                    step_id="pair",
                    description_placeholders={
                        "name": self._discovery_info.name
                        or self._discovery_info.address
                    },
                )
            self._pairing_started = True

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
                    _firmware_version,
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

                # Store button UUID for firmware updates
                if button_uuid is not None:
                    entry_data[CONF_BUTTON_UUID] = button_uuid.hex()

                return self.async_create_entry(
                    title=title,
                    data=entry_data,
                )

            except TimeoutError, BleakError:
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

        # Allow the user to retry after an error
        self._pairing_started = False

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
                    vol.Required(
                        CONF_PUSH_TWIST_MODE, default=current_mode
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=PushTwistMode.DEFAULT,
                                    label="default",
                                ),
                                SelectOptionDict(
                                    value=PushTwistMode.CONTINUOUS,
                                    label="continuous",
                                ),
                                SelectOptionDict(
                                    value=PushTwistMode.SELECTOR,
                                    label="selector",
                                ),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key=CONF_PUSH_TWIST_MODE,
                        )
                    ),
                }
            ),
        )
