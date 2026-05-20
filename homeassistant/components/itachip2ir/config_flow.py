"""Config flow for the iTach IP2IR integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DISCOVERY, DOMAIN
from .discovery import ItachDiscovery, async_wait_for_device_id
from .options_flow import ItachOptionsFlow
from .pyitach import (
    DEFAULT_PORT,
    ItachBusyError,
    ItachClient,
    ItachCommandError,
    ItachConnectionError,
    ItachError,
    ItachResponseError,
    async_get_ir_capability,
    normalize_device_id as _pyitach_normalize_device_id,
)

_LOGGER = logging.getLogger(__name__)

CONF_IR_MODULE = "ir_module"
CONF_IR_PORTS = "ir_ports"
CONF_IR_ENABLED_PORTS = "ir_enabled_ports"
CONF_IR_CONNECTOR_MODES = "ir_connector_modes"


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class CannotIdentify(Exception):
    """Error to indicate we could not determine a stable device ID."""


class InvalidDeviceId(Exception):
    """Error to indicate the user-entered device ID is invalid."""


class NoIrPorts(Exception):
    """Error to indicate the device has no usable IR output ports."""


def _raise_no_ir_ports() -> None:
    """Raise when the device has no usable IR output ports."""
    raise NoIrPorts


def _user_schema(
    host: str = "",
    port: int = DEFAULT_PORT,
    device_id: str = "",
) -> vol.Schema:
    """Return user step schema with defaults."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Optional(CONF_PORT, default=port): int,
            vol.Optional(CONF_DEVICE_ID, default=device_id): str,
        }
    )


def _connection_schema(host: str, port: int = DEFAULT_PORT) -> vol.Schema:
    """Return host/port schema."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): int,
        }
    )


def _normalize_device_id(value: str | None) -> str | None:
    """Normalize user-entered device ID into GlobalCache_XXXXXXXXXXXX.

    Accepts GlobalCache_XXXXXXXXXXXX, raw 12-character IDs, and MAC-style
    colon/dash-separated values. The MAC-style input is only a convenience; the
    canonical config-entry identity is the Global Caché UUID.
    """
    if value is None or not value.strip():
        return None

    normalized = _pyitach_normalize_device_id(value)
    if normalized is None:
        raise InvalidDeviceId

    return normalized


async def _validate_device(host: str, port: int) -> dict[str, Any]:
    """Validate that the target is a reachable IR-capable iTach device."""
    _LOGGER.debug("Validating iTach IR capability at %s:%s", host, port)

    client = ItachClient(host, port)

    try:
        ir_capability = await async_get_ir_capability(client)

        if not ir_capability.enabled_ports:
            _raise_no_ir_ports()

        if all(mode == "UNKNOWN" for mode in ir_capability.connector_modes.values()):
            _LOGGER.info(
                "Could not determine iTach IR connector output modes for %s:%s; "
                "falling back to all %s connector(s)",
                host,
                port,
                ir_capability.ports,
            )
    except NoIrPorts:
        raise
    except ItachConnectionError as err:
        _LOGGER.debug(
            "Failed connecting to iTach while validating IR capability at %s:%s: %s",
            host,
            port,
            err,
        )
        raise CannotConnect from err
    except ItachCommandError as err:
        _LOGGER.debug(
            "iTach command error while validating IR capability at %s:%s: %s",
            host,
            port,
            err,
        )
        if err.command == "getdevices\r" and err.response == "No IR module found":
            raise NoIrPorts from err
        raise
    except (ItachBusyError, ItachResponseError, ValueError) as err:
        _LOGGER.debug(
            "Unexpected iTach protocol response while validating IR capability at "
            "%s:%s: %s",
            host,
            port,
            err,
        )
        raise
    except ItachError as err:
        _LOGGER.debug(
            "Failed communicating with iTach while validating IR capability at "
            "%s:%s: %s",
            host,
            port,
            err,
        )
        raise CannotConnect from err
    else:
        return {
            CONF_IR_MODULE: ir_capability.module,
            CONF_IR_PORTS: ir_capability.ports,
            CONF_IR_CONNECTOR_MODES: ir_capability.connector_modes,
            CONF_IR_ENABLED_PORTS: ir_capability.enabled_ports,
        }
    finally:
        await client.close()


async def _identify_device(
    host: str,
    user_device_id: str | None,
    discovery: ItachDiscovery | None = None,
) -> str:
    """Determine stable device ID using user ID, discovery cache, or fallback UDP."""
    normalized = _normalize_device_id(user_device_id)
    if normalized is not None:
        return normalized

    discovered_id = await async_wait_for_device_id(
        host,
        timeout=10.0,
        discovery=discovery,
    )
    if discovered_id is not None:
        return discovered_id

    raise CannotIdentify


async def _validate_manual_input(
    host: str,
    port: int,
    user_device_id: str | None,
    discovery: ItachDiscovery | None = None,
) -> dict[str, Any]:
    """Validate manual setup input and determine a stable unique ID."""
    device_info = await _validate_device(host, port)
    unique_id = await _identify_device(host, user_device_id, discovery)

    return {
        "title": f"iTach IP2IR ({host})",
        "unique_id": unique_id,
        **device_info,
    }


def _get_discovery(hass: HomeAssistant) -> ItachDiscovery | None:
    """Return the running discovery listener, if available."""
    discovery = hass.data.get(DOMAIN, {}).get(DISCOVERY)
    if isinstance(discovery, ItachDiscovery):
        return discovery
    return None


async def _validate_discovered_input(
    host: str,
    port: int,
    unique_id: str,
) -> dict[str, Any]:
    """Validate a discovered device using the beacon-provided unique ID."""
    device_info = await _validate_device(host, port)
    canonical_unique_id = _normalize_device_id(unique_id)
    if canonical_unique_id is None:
        raise CannotIdentify

    return {
        "title": f"iTach IP2IR ({host})",
        "unique_id": canonical_unique_id,
        **device_info,
    }


class Itachip2irConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iTach IP2IR."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovery_info: dict[str, str | int] | None = None

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ItachOptionsFlow:
        """Create the options flow."""
        return ItachOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, str | int] | None = None,
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}

        host = ""
        port = DEFAULT_PORT
        device_id_value = ""

        if user_input is not None:
            host = str(user_input.get(CONF_HOST, ""))
            port = int(user_input.get(CONF_PORT, DEFAULT_PORT))

            raw_device_id = user_input.get(CONF_DEVICE_ID)
            device_id_value = str(raw_device_id) if raw_device_id else ""

            try:
                info = await _validate_manual_input(
                    host,
                    port,
                    device_id_value or None,
                    _get_discovery(self.hass),
                )
            except InvalidDeviceId:
                errors[CONF_DEVICE_ID] = "invalid_device_id"
            except CannotIdentify:
                errors["base"] = "cannot_identify"
            except NoIrPorts:
                errors["base"] = "no_ir_ports"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during iTach setup")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(info["unique_id"]))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=str(info["title"]),
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_IR_MODULE: int(info[CONF_IR_MODULE]),
                        CONF_IR_PORTS: int(info[CONF_IR_PORTS]),
                        CONF_IR_ENABLED_PORTS: list(info[CONF_IR_ENABLED_PORTS]),
                        CONF_IR_CONNECTOR_MODES: dict(info[CONF_IR_CONNECTOR_MODES]),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(host=host, port=port, device_id=device_id_value),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, str | int] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing iTach entry."""
        entry = self._get_reconfigure_entry()

        host = str(entry.data[CONF_HOST])
        port = int(entry.data.get(CONF_PORT, DEFAULT_PORT))
        errors: dict[str, str] = {}

        if user_input is not None:
            host = str(user_input[CONF_HOST])
            port = int(user_input[CONF_PORT])

            if host == str(entry.data[CONF_HOST]) and port == int(
                entry.data.get(CONF_PORT, DEFAULT_PORT)
            ):
                return self.async_abort(reason="no_changes")

            try:
                info = await _validate_device(host, port)
            except NoIrPorts:
                errors["base"] = "no_ir_ports"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during iTach reconfiguration")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_IR_MODULE: int(info[CONF_IR_MODULE]),
                        CONF_IR_PORTS: int(info[CONF_IR_PORTS]),
                        CONF_IR_ENABLED_PORTS: list(info[CONF_IR_ENABLED_PORTS]),
                        CONF_IR_CONNECTOR_MODES: dict(info[CONF_IR_CONNECTOR_MODES]),
                    },
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(host, port),
            errors=errors,
        )

    async def async_step_dhcp(
        self,
        discovery_info: DhcpServiceInfo,
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        host = discovery_info.ip
        macaddress = discovery_info.macaddress

        try:
            unique_id = _normalize_device_id(macaddress)
        except InvalidDeviceId:
            return self.async_abort(reason="cannot_identify")

        if unique_id is None:
            return self.async_abort(reason="cannot_identify")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        try:
            await _validate_discovered_input(
                host=host,
                port=DEFAULT_PORT,
                unique_id=unique_id,
            )
        except CannotIdentify:
            return self.async_abort(reason="cannot_identify")
        except NoIrPorts:
            return self.async_abort(reason="no_ir_ports")
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected error during DHCP discovery")
            return self.async_abort(reason="unknown")

        self._discovery_info = {
            CONF_HOST: host,
            CONF_PORT: DEFAULT_PORT,
            "unique_id": unique_id,
        }

        return await self.async_step_confirm_discovery()

    async def async_step_discovery(
        self,
        discovery_info: dict[str, str | int],
    ) -> ConfigFlowResult:
        """Handle discovery from UDP beacon listener."""
        host = str(discovery_info[CONF_HOST])
        port = int(discovery_info.get(CONF_PORT, DEFAULT_PORT))

        try:
            unique_id = _normalize_device_id(str(discovery_info["unique_id"]))
        except InvalidDeviceId:
            return self.async_abort(reason="cannot_identify")

        if unique_id is None:
            return self.async_abort(reason="cannot_identify")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        self._discovery_info = {
            CONF_HOST: host,
            CONF_PORT: port,
            "unique_id": unique_id,
        }

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self,
        user_input: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Confirm adding a discovered device."""
        if self._discovery_info is None:
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}

        if user_input is not None:
            host = str(self._discovery_info[CONF_HOST])
            port = int(self._discovery_info[CONF_PORT])
            unique_id = str(self._discovery_info["unique_id"])

            try:
                info = await _validate_discovered_input(
                    host=host,
                    port=port,
                    unique_id=unique_id,
                )
            except CannotIdentify:
                errors["base"] = "cannot_identify"
            except NoIrPorts:
                errors["base"] = "no_ir_ports"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error confirming discovered iTach")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(info["unique_id"]))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=str(info["title"]),
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_IR_MODULE: int(info[CONF_IR_MODULE]),
                        CONF_IR_PORTS: int(info[CONF_IR_PORTS]),
                        CONF_IR_ENABLED_PORTS: list(info[CONF_IR_ENABLED_PORTS]),
                        CONF_IR_CONNECTOR_MODES: dict(info[CONF_IR_CONNECTOR_MODES]),
                    },
                )

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={"host": str(self._discovery_info[CONF_HOST])},
            errors=errors,
        )
