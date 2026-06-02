"""Config flow for Avea."""

from contextlib import suppress
import logging
from typing import Any

import avea
from bleak.exc import BleakError
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import AVEA_SERVICE_UUID, DOMAIN, UNKNOWN_NAME

_LOGGER = logging.getLogger(__name__)


def _normalize_name(name: str | None) -> str | None:
    """Return a valid Avea name."""
    if not name or name == UNKNOWN_NAME:
        return None
    return name


def _validate_device(discovery_info: BluetoothServiceInfoBleak) -> str:
    """Validate the device is reachable and return a title for it."""
    bulb = avea.Bulb(discovery_info.device)

    try:
        if not bulb.connect():
            raise CannotConnect

        try:
            name = bulb.get_name()
        except BleakError, OSError, RuntimeError:
            _LOGGER.debug(
                "Failed to get name for Avea device %s",
                discovery_info.address,
                exc_info=True,
            )
            name = None
        brightness = bulb.get_brightness()
    except (BleakError, OSError, RuntimeError) as err:
        raise CannotConnect from err
    finally:
        with suppress(BleakError, OSError, RuntimeError):
            bulb.close()

    if brightness is None:
        raise CannotConnect

    return (
        _normalize_name(name)
        or _normalize_name(discovery_info.name)
        or discovery_info.address
    )


def _is_avea_discovery(discovery_info: BluetoothServiceInfoBleak) -> bool:
    """Return if the bluetooth discovery matches an Avea bulb."""
    return AVEA_SERVICE_UUID in discovery_info.service_uuids


def _discovery_label(discovery_info: BluetoothServiceInfoBleak) -> str:
    """Return a label for a discovered Avea bulb."""
    if (
        name := _normalize_name(discovery_info.name)
    ) and name != discovery_info.address:
        return f"{name} ({discovery_info.address})"
    return discovery_info.address


class AveaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Avea."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered device before creating the entry."""
        assert self._discovery_info is not None

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                title = await self.hass.async_add_executor_job(
                    _validate_device, self._discovery_info
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while validating Avea device")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=title,
                    data={CONF_ADDRESS: self._discovery_info.address},
                )

        self.context["title_placeholders"] = {
            "name": self._discovery_info.name or self._discovery_info.address
        }
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick a discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            discovery_info = self._discovered_devices[address]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            try:
                title = await self.hass.async_add_executor_job(
                    _validate_device, discovery_info
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while validating Avea device")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=title,
                    data={CONF_ADDRESS: address},
                )

        if discovery := self._discovery_info:
            self._discovered_devices[discovery.address] = discovery
        else:
            await bluetooth.async_request_active_scan(self.hass)
            current_addresses = self._async_current_ids(include_ignore=False)
            for discovery in async_discovered_service_info(self.hass):
                if (
                    discovery.address in current_addresses
                    or discovery.address in self._discovered_devices
                    or not _is_avea_discovery(discovery)
                ):
                    continue
                self._discovered_devices[discovery.address] = discovery

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        if self._discovery_info:
            disc = self._discovery_info
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_ADDRESS, default=disc.address): vol.In(
                        {disc.address: _discovery_label(disc)}
                    )
                }
            )
        else:
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            service_info.address: _discovery_label(service_info)
                            for service_info in self._discovered_devices.values()
                        }
                    ),
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML."""
        address = import_data[CONF_ADDRESS]

        await self.async_set_unique_id(address, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=import_data.get(CONF_NAME, address),
            data={CONF_ADDRESS: address},
        )


class CannotConnect(Exception):
    """Error to indicate an Avea device cannot be connected to."""
