"""Config flow for ISEO Argo BLE Lock."""

from __future__ import annotations

import logging
from typing import Any
import uuid as uuid_module

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from iseo_argo_ble import (
    IseoAuthError,
    IseoClient,
    IseoConnectionError,
    is_iseo_advertisement,
)
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ADDRESS,
    CONF_PRIV_SCALAR,
    CONF_UUID,
    DEFAULT_USER_SUBTYPE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _generate_identity() -> ec.EllipticCurvePrivateKey:
    """Generate a fresh SECP224R1 private key for use as an Argo BT identity."""
    priv = ec.generate_private_key(ec.SECP224R1(), default_backend())
    if not isinstance(priv, ec.EllipticCurvePrivateKey):
        raise TypeError("Expected EllipticCurvePrivateKey")
    return priv


def _discover_locks(hass: HomeAssistant) -> list[BluetoothServiceInfoBleak]:
    """Query HA's bluetooth integration for nearby ISEO locks."""
    all_devices = sorted(
        async_discovered_service_info(hass, connectable=True),
        key=lambda i: i.rssi,
        reverse=True,
    )
    _LOGGER.debug(
        "HA bluetooth cache — %d connectable device(s) visible", len(all_devices)
    )

    found: list[BluetoothServiceInfoBleak] = []
    for info in all_devices:
        if not is_iseo_advertisement(list(info.service_uuids or [])):
            continue
        _LOGGER.debug(
            "  %s  name=%r  rssi=%d — ISEO lock",
            info.address,
            info.name,
            info.rssi,
        )
        found.append(info)

    return found


class IseoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for ISEO Argo BLE Lock."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}
        self._address: str = ""
        self._device_name: str = ""
        self._uuid_hex: str = ""
        self._priv_scalar: str = ""
        self._gw_priv: ec.EllipticCurvePrivateKey | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a lock from HA's BLE cache."""
        errors: dict[str, str] = {}

        if user_input is not None and CONF_ADDRESS in user_input:
            address = user_input[CONF_ADDRESS]

            await self.async_set_unique_id(address.replace(":", ""))
            self._abort_if_unique_id_configured()

            priv = _generate_identity()
            priv_int = priv.private_numbers().private_value
            new_uuid = uuid_module.uuid4().bytes

            self._address = address
            self._device_name = (
                self._discovered[address].name if address in self._discovered else ""
            )
            self._uuid_hex = new_uuid.hex()
            self._priv_scalar = hex(priv_int)
            self._gw_priv = priv

            return await self.async_step_gw_register()

        found = _discover_locks(self.hass)
        self._discovered = {info.address: info for info in found}

        if not self._discovered:
            errors["base"] = "no_devices_found"
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        configured = {
            entry.data.get(CONF_ADDRESS) for entry in self._async_current_entries()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=info.address,
                                    label=(
                                        f"{info.name or 'Unknown'}  —  {info.address}"
                                        f"  (RSSI {info.rssi} dBm)"
                                        + (
                                            " — already configured"
                                            if info.address in configured
                                            else ""
                                        )
                                    ),
                                )
                                for info in found
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Called by HA when a matching BLE advertisement is seen."""
        await self.async_set_unique_id(discovery_info.address.replace(":", ""))
        self._abort_if_unique_id_configured()

        if not is_iseo_advertisement(list(discovery_info.service_uuids or [])):
            return self.async_abort(reason="not_iseo_device")

        priv = _generate_identity()
        priv_int = priv.private_numbers().private_value
        new_uuid = uuid_module.uuid4().bytes

        self._address = discovery_info.address
        self._device_name = discovery_info.name or discovery_info.address
        self._uuid_hex = new_uuid.hex()
        self._priv_scalar = hex(priv_int)
        self._gw_priv = priv

        self.context["title_placeholders"] = {"name": self._device_name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered lock before proceeding to enrollment."""
        if user_input is not None:
            return await self.async_step_gw_register()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._device_name},
        )

    async def async_step_gw_register(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Register the UUID as a gateway (requires Master Card)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (
                ble_device := async_ble_device_from_address(
                    self.hass, self._address, connectable=True
                )
            ):
                errors["base"] = "cannot_connect"
            else:
                client = IseoClient(
                    address=self._address,
                    uuid_bytes=bytes.fromhex(self._uuid_hex),
                    identity_priv=self._gw_priv,
                    subtype=DEFAULT_USER_SUBTYPE,
                    ble_device=ble_device,
                )
                try:
                    await client.register_user(name="Home Assistant")
                    return await self.async_step_gw_register_logs()
                except IseoConnectionError:
                    errors["base"] = "cannot_connect"
                except IseoAuthError as exc:
                    _LOGGER.error("Gateway registration failed: %s", exc)
                    errors["base"] = "auth_failed"
                except Exception:
                    _LOGGER.exception("Unexpected error during gateway registration")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="gw_register",
            description_placeholders={"uuid": self._uuid_hex.upper()},
            errors=errors,
        )

    async def async_step_gw_register_logs(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enable log notifications for the gateway (requires Master Card)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (
                ble_device := async_ble_device_from_address(
                    self.hass, self._address, connectable=True
                )
            ):
                errors["base"] = "cannot_connect"
            else:
                client = IseoClient(
                    address=self._address,
                    uuid_bytes=bytes.fromhex(self._uuid_hex),
                    identity_priv=self._gw_priv,
                    subtype=DEFAULT_USER_SUBTYPE,
                    ble_device=ble_device,
                )
                try:
                    await client.gw_register_log_notif()
                    return self._async_create_iseo_entry()
                except IseoConnectionError:
                    errors["base"] = "cannot_connect"
                except IseoAuthError as exc:
                    _LOGGER.error("Gateway log registration failed: %s", exc)
                    errors["base"] = "auth_failed"
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error during gateway log registration"
                    )
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="gw_register_logs",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    def _async_create_iseo_entry(self) -> ConfigFlowResult:
        """Create the final config entry."""
        return self.async_create_entry(
            title=self._device_name or f"ISEO Lock ({self._address})",
            data={
                CONF_ADDRESS: self._address,
                CONF_UUID: self._uuid_hex,
                CONF_PRIV_SCALAR: self._priv_scalar,
            },
        )
