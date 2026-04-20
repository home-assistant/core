"""Config flow for the EARN-E P1 Meter integration."""

from __future__ import annotations

import logging
from typing import Any

from earn_e_p1 import EarnEP1Device, EarnEP1Listener, discover, validate
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 10
VALIDATION_TIMEOUT = 65

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class EarnEP1ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EARN-E P1 Meter."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: EarnEP1Device | None = None
        self._discovered_mac: str | None = None

    async def _async_discover(self) -> EarnEP1Device | None:
        """Discover an EARN-E device on the network."""
        listener: EarnEP1Listener | None = self.hass.data.get(DOMAIN)
        if listener is not None:
            devices = await listener.discover(timeout=DISCOVERY_TIMEOUT)
        else:
            try:
                devices = await discover(timeout=DISCOVERY_TIMEOUT)
            except OSError:
                return None
        return devices[0] if devices else None

    async def _async_validate_host(self, host: str) -> EarnEP1Device | None:
        """Validate a host and wait for a packet containing its serial.

        Uses the shared listener if available, otherwise creates a temporary one.
        Returns the device if serial is found, None on timeout.
        """
        listener: EarnEP1Listener | None = self.hass.data.get(DOMAIN)
        if listener is not None:
            return await listener.validate(host, timeout=VALIDATION_TIMEOUT)
        return await validate(host, timeout=VALIDATION_TIMEOUT)

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery of an EARN-E P1 meter."""
        ip = discovery_info.ip
        raw_mac = discovery_info.macaddress
        formatted_mac = format_mac(raw_mac)

        for entry in self._async_current_entries(include_ignore=False):
            entry_mac = entry.data.get(CONF_MAC)
            if entry_mac and format_mac(entry_mac) == formatted_mac:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_HOST: ip, CONF_MAC: raw_mac},
                    reason="already_configured",
                )

        try:
            device = await self._async_validate_host(ip)
        except OSError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected error validating DHCP-discovered device")
            return self.async_abort(reason="unknown")

        if device is None:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(device.serial)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: ip, CONF_MAC: raw_mac},
        )

        self._discovered_device = device
        self._discovered_mac = raw_mac
        self.context["title_placeholders"] = {"host": ip}
        return await self.async_step_discovery_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return await self._async_validate_and_create(user_input)

        # Attempt auto-discovery before showing manual form
        device = await self._async_discover()
        if device:
            self._discovered_device = device
            return await self.async_step_discovery_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        )

    async def _async_validate_and_create(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Validate manual IP entry and create config entry."""
        errors: dict[str, str] = {}
        host = user_input[CONF_HOST]

        try:
            device = await self._async_validate_host(host)
        except OSError:
            errors["base"] = "cannot_connect"
            device = None
        except Exception:
            _LOGGER.exception("Unexpected error validating device")
            errors["base"] = "unknown"
            device = None

        if device is None and "base" not in errors:
            errors["base"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        assert device is not None
        await self.async_set_unique_id(device.serial)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"EARN-E P1 ({host})",
            data={CONF_HOST: host, CONF_SERIAL: device.serial},
        )

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of a discovered device."""
        assert self._discovered_device is not None
        device = self._discovered_device

        if user_input is not None:
            # If discovery already got the serial, use it directly
            if device.serial:
                await self.async_set_unique_id(device.serial)
                self._abort_if_unique_id_configured()
                data: dict[str, Any] = {
                    CONF_HOST: device.host,
                    CONF_SERIAL: device.serial,
                }
                if self._discovered_mac is not None:
                    data[CONF_MAC] = self._discovered_mac
                return self.async_create_entry(
                    title=f"EARN-E P1 ({device.host})",
                    data=data,
                )

            # Discovery didn't get serial — validate to obtain it
            try:
                validated = await self._async_validate_host(device.host)
            except OSError:
                validated = None
            except Exception:
                _LOGGER.exception("Unexpected error validating device")
                return self.async_abort(reason="unknown")

            if validated is None:
                return self.async_abort(reason="cannot_connect")

            await self.async_set_unique_id(validated.serial)
            self._abort_if_unique_id_configured()
            data = {CONF_HOST: validated.host, CONF_SERIAL: validated.serial}
            if self._discovered_mac is not None:
                data[CONF_MAC] = self._discovered_mac
            return self.async_create_entry(
                title=f"EARN-E P1 ({validated.host})",
                data=data,
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": device.host},
        )
