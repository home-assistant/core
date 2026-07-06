"""Config flow for Besen."""

import logging
from typing import TYPE_CHECKING, Any, override

from besen.client import BesenClient
from besen.const import DEFAULT_PIN
from besen.exceptions import CannotConnect, InvalidAuth, NoConnectablePath
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import DOMAIN

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

    from homeassistant.config_entries import ConfigFlowResult

_LOGGER = logging.getLogger(__name__)


def _normalize_address(address: str) -> str:
    """Normalize a Bluetooth address."""

    return address.strip().upper()


PIN_SCHEMA = vol.All(
    selector.TextSelector(
        selector.TextSelectorConfig(
            type=selector.TextSelectorType.PASSWORD,
        )
    ),
    vol.Match(r"^\d{6}$"),
)

MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDRESS): selector.TextSelector(),
        vol.Required(CONF_PIN, default=DEFAULT_PIN): PIN_SCHEMA,
    }
)

PIN_ONLY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PIN, default=DEFAULT_PIN): PIN_SCHEMA,
    }
)


async def _async_validate_input(
    hass: HomeAssistant,
    *,
    address: str,
    pin: str,
    name: str | None,
) -> str:
    """Validate setup by logging into the charger."""

    def _ble_device_provider() -> BLEDevice | None:
        return bluetooth.async_ble_device_from_address(
            hass,
            address,
            connectable=True,
        )

    if _ble_device_provider() is None:
        await bluetooth.async_request_active_scan(hass)

    if _ble_device_provider() is None:
        raise NoConnectablePath("No connectable Bluetooth path is available")

    client = BesenClient(
        address=address,
        pin=pin,
        ble_device_provider=_ble_device_provider,
        logger=_LOGGER,
        advertised_name=name,
    )
    try:
        await client.async_start()
        info = client.state.info
        return info.model or name or address
    finally:
        await client.async_stop()


class BesenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Besen config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""

        self._discovered_address: str | None = None
        self._discovered_name: str | None = None

    @override
    async def async_step_bluetooth(
        self,
        discovery_info: BluetoothServiceInfoBleak,
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""

        if not (discovery_info.name or "").startswith("ACP#"):
            return self.async_abort(reason="not_supported")

        address = _normalize_address(discovery_info.address)
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured(
            updates={
                CONF_ADDRESS: address,
                CONF_NAME: discovery_info.name,
            }
        )
        self._discovered_address = address
        self._discovered_name = discovery_info.name
        self.context["title_placeholders"] = {
            "name": discovery_info.name or address,
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Confirm a discovered charger."""

        assert self._discovered_address is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            pin = user_input[CONF_PIN]
            try:
                title = await _async_validate_input(
                    self.hass,
                    address=self._discovered_address,
                    pin=pin,
                    name=self._discovered_name,
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoConnectablePath:
                errors["base"] = "no_connectable_path"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected Besen setup error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_ADDRESS: self._discovered_address,
                        CONF_NAME: self._discovered_name,
                        CONF_PIN: pin,
                    },
                )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=PIN_ONLY_SCHEMA,
            errors=errors,
        )

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle manual setup."""

        errors: dict[str, str] = {}
        if user_input is not None:
            address = _normalize_address(user_input[CONF_ADDRESS])
            pin = user_input[CONF_PIN]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            try:
                title = await _async_validate_input(
                    self.hass,
                    address=address,
                    pin=pin,
                    name=None,
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoConnectablePath:
                errors["base"] = "no_connectable_path"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected Besen setup error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_ADDRESS: address,
                        CONF_PIN: pin,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=MANUAL_SCHEMA,
            errors=errors,
        )
