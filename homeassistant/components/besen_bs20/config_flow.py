"""Config flow for Besen BS20."""

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, override

from besen_bs20.client import BesenBS20Client
from besen_bs20.const import DEFAULT_PIN
from besen_bs20.exceptions import CannotConnect, InvalidAuth, NoConnectablePath
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import CONF_SYNC_CLOCK, DEFAULT_SYNC_CLOCK, DOMAIN

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

    from homeassistant.config_entries import ConfigFlowResult

_LOGGER = logging.getLogger(__name__)


def _normalize_address(address: str) -> str:
    """Normalize a Bluetooth address."""

    return address.strip().upper()


def _pin_schema() -> selector.TextSelector:
    """Return a password text selector for PIN fields."""

    return selector.TextSelector(
        selector.TextSelectorConfig(
            type=selector.TextSelectorType.PASSWORD,
        )
    )


def _manual_schema() -> vol.Schema:
    """Return manual setup schema."""

    return vol.Schema(
        {
            vol.Required(CONF_ADDRESS): selector.TextSelector(),
            vol.Required(CONF_PIN, default=DEFAULT_PIN): _pin_schema(),
            vol.Optional(CONF_SYNC_CLOCK, default=DEFAULT_SYNC_CLOCK): bool,
        }
    )


def _pin_only_schema() -> vol.Schema:
    """Return PIN-only setup schema."""

    return vol.Schema(
        {
            vol.Required(CONF_PIN, default=DEFAULT_PIN): _pin_schema(),
            vol.Optional(CONF_SYNC_CLOCK, default=DEFAULT_SYNC_CLOCK): bool,
        }
    )


async def _async_validate_input(
    hass: HomeAssistant,
    *,
    address: str,
    pin: str,
    name: str | None,
    sync_clock: bool,
) -> str:
    """Validate setup by logging into the charger."""

    if len(pin) != 6 or not pin.isdigit():
        raise InvalidAuth("PIN must be exactly 6 digits")

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

    client = BesenBS20Client(
        address=address,
        pin=pin,
        ble_device_provider=_ble_device_provider,
        logger=_LOGGER,
        advertised_name=name,
        sync_clock=sync_clock,
    )
    try:
        await client.async_start()
        info = client.state.info
        return info.model or name or address
    finally:
        await client.async_stop()


class BesenBS20ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Besen BS20 config flow."""

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
            sync_clock = user_input.get(CONF_SYNC_CLOCK, DEFAULT_SYNC_CLOCK)
            try:
                title = await _async_validate_input(
                    self.hass,
                    address=self._discovered_address,
                    pin=pin,
                    name=self._discovered_name,
                    sync_clock=sync_clock,
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoConnectablePath as err:
                _LOGGER.warning(
                    "Besen BS20 setup failed for %s: %s",
                    self._discovered_address,
                    err,
                )
                errors["base"] = "no_connectable_path"
            except CannotConnect as err:
                _LOGGER.warning(
                    "Besen BS20 setup failed for %s: %s",
                    self._discovered_address,
                    err,
                )
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected Besen BS20 setup error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_ADDRESS: self._discovered_address,
                        CONF_NAME: self._discovered_name,
                        CONF_PIN: pin,
                    },
                    options={CONF_SYNC_CLOCK: sync_clock},
                )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=_pin_only_schema(),
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
            sync_clock = user_input.get(CONF_SYNC_CLOCK, DEFAULT_SYNC_CLOCK)
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            try:
                title = await _async_validate_input(
                    self.hass,
                    address=address,
                    pin=pin,
                    name=None,
                    sync_clock=sync_clock,
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoConnectablePath as err:
                _LOGGER.warning("Besen BS20 setup failed for %s: %s", address, err)
                errors["base"] = "no_connectable_path"
            except CannotConnect as err:
                _LOGGER.warning("Besen BS20 setup failed for %s: %s", address, err)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected Besen BS20 setup error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_ADDRESS: address,
                        CONF_PIN: pin,
                    },
                    options={CONF_SYNC_CLOCK: sync_clock},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_manual_schema(),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Handle reauthentication."""

        self._discovered_address = entry_data[CONF_ADDRESS]
        self._discovered_name = entry_data.get(CONF_NAME)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Ask the user for a new PIN."""

        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        address = entry.data[CONF_ADDRESS]
        if user_input is not None:
            pin = user_input[CONF_PIN]
            try:
                await _async_validate_input(
                    self.hass,
                    address=address,
                    pin=pin,
                    name=entry.data.get(CONF_NAME),
                    sync_clock=entry.options.get(CONF_SYNC_CLOCK, DEFAULT_SYNC_CLOCK),
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoConnectablePath as err:
                _LOGGER.warning("Besen BS20 reauth failed for %s: %s", address, err)
                errors["base"] = "no_connectable_path"
            except CannotConnect as err:
                _LOGGER.warning("Besen BS20 reauth failed for %s: %s", address, err)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected Besen BS20 reauth error")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PIN: pin},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PIN): _pin_schema()}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle UI reconfiguration."""

        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            pin = user_input[CONF_PIN]
            sync_clock = user_input.get(CONF_SYNC_CLOCK, DEFAULT_SYNC_CLOCK)
            try:
                await _async_validate_input(
                    self.hass,
                    address=entry.data[CONF_ADDRESS],
                    pin=pin,
                    name=entry.data.get(CONF_NAME),
                    sync_clock=sync_clock,
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoConnectablePath as err:
                _LOGGER.warning(
                    "Besen BS20 reconfigure failed for %s: %s",
                    entry.data[CONF_ADDRESS],
                    err,
                )
                errors["base"] = "no_connectable_path"
            except CannotConnect as err:
                _LOGGER.warning(
                    "Besen BS20 reconfigure failed for %s: %s",
                    entry.data[CONF_ADDRESS],
                    err,
                )
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected Besen BS20 reconfigure error")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PIN: pin},
                    options={CONF_SYNC_CLOCK: sync_clock},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN, default=entry.data[CONF_PIN]): _pin_schema(),
                    vol.Optional(
                        CONF_SYNC_CLOCK,
                        default=entry.options.get(
                            CONF_SYNC_CLOCK,
                            DEFAULT_SYNC_CLOCK,
                        ),
                    ): bool,
                }
            ),
            errors=errors,
        )
