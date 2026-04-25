"""Config flow for Hue BLE integration."""

from __future__ import annotations

from enum import Enum
import logging
from typing import Any

from bleak.backends.scanner import AdvertisementData
from HueBLE import ConnectionError, HueBleError, HueBleLight, PairingError
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.api import (
    async_ble_device_from_address,
    async_scanner_count,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, URL_FACTORY_RESET, URL_PAIRING_MODE
from .light import get_available_color_modes

_LOGGER = logging.getLogger(__name__)


SERVICE_UUID = SERVICE_DATA_UUID = "0000fe0f-0000-1000-8000-00805f9b34fb"


def device_filter(advertisement_data: AdvertisementData) -> bool:
    """Return True if the device is supported."""
    return (
        SERVICE_UUID in advertisement_data.service_uuids
        and SERVICE_DATA_UUID in advertisement_data.service_data
    )


async def validate_input(hass: HomeAssistant, address: str) -> Error | None:
    """Return error if cannot connect and validate."""

    ble_device = async_ble_device_from_address(hass, address.upper(), connectable=True)

    if ble_device is None:
        count_scanners = async_scanner_count(hass, connectable=True)
        _LOGGER.debug("Count of BLE scanners in HA bt: %i", count_scanners)

        if count_scanners < 1:
            return Error.NO_SCANNERS
        return Error.NOT_FOUND

    try:
        light = HueBleLight(ble_device)
        await light.connect()
        get_available_color_modes(light)
        await light.poll_state()

    except ConnectionError as e:
        _LOGGER.exception("Error connecting to light")
        return (
            Error.INVALID_AUTH
            if type(e.__cause__) is PairingError
            else Error.CANNOT_CONNECT
        )
    except HueBleError:
        _LOGGER.exception("Unexpected error validating light connection")
        return Error.UNKNOWN
    except HomeAssistantError:
        return Error.NOT_SUPPORTED
    else:
        return None
    finally:
        await light.disconnect()


class HueBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hue BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, bluetooth.BluetoothServiceInfoBleak] = {}
        self._discovery_info: bluetooth.BluetoothServiceInfoBleak | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = dr.format_mac(user_input[CONF_MAC])
            # Don't raise on progress because there may be discovery flows
            await self.async_set_unique_id(unique_id, raise_on_progress=False)
            # Guard against the user selecting a device which has been configured by
            # another flow.
            self._abort_if_unique_id_configured()
            self._discovery_info = self._discovered_devices[user_input[CONF_MAC]]
            return await self.async_step_confirm()

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery in bluetooth.async_discovered_service_info(self.hass):
            if (
                discovery.address in current_addresses
                or discovery.address in self._discovered_devices
                or not device_filter(discovery.advertisement)
            ):
                continue
            self._discovered_devices[discovery.address] = discovery

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_MAC): vol.In(
                    {
                        service_info.address: (
                            f"{service_info.name} ({service_info.address})"
                        )
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

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the home assistant scanner."""

        _LOGGER.debug(
            "HA found light %s. Use user flow to show in UI and connect",
            discovery_info.name,
        )
        return self.async_abort(reason="discovery_unsupported")

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a single device."""

        assert self._discovery_info is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = dr.format_mac(self._discovery_info.address)
            # Don't raise on progress because there may be discovery flows
            await self.async_set_unique_id(unique_id, raise_on_progress=False)
            # Guard against the user selecting a device which has been configured by
            # another flow.
            self._abort_if_unique_id_configured()
            error = await validate_input(self.hass, unique_id)
            if error:
                errors["base"] = error.value
            else:
                return self.async_create_entry(title=self._discovery_info.name, data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                CONF_NAME: self._discovery_info.name,
                CONF_MAC: self._discovery_info.address,
                "url_pairing_mode": URL_PAIRING_MODE,
                "url_factory_reset": URL_FACTORY_RESET,
            },
        )


class Error(Enum):
    """Potential validation errors when attempting to connect."""

    CANNOT_CONNECT = "cannot_connect"
    """Error to indicate we cannot connect."""

    INVALID_AUTH = "invalid_auth"
    """Error to indicate there is invalid auth."""

    NO_SCANNERS = "no_scanners"
    """Error to indicate no bluetooth scanners are available."""

    NOT_FOUND = "not_found"
    """Error to indicate the light could not be found."""

    NOT_SUPPORTED = "not_supported"
    """Error to indicate that the light is not a supported model."""

    UNKNOWN = "unknown"
    """Error to indicate that the issue is unknown."""
