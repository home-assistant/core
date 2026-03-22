"""Config flow for the EARN-E P1 Meter integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from earn_e_p1 import DEFAULT_PORT, EarnEP1Device, EarnEP1Listener, discover
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN

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
        loop = asyncio.get_running_loop()
        found: asyncio.Future[EarnEP1Device] = loop.create_future()

        def on_update(device: EarnEP1Device, raw: dict[str, Any]) -> None:
            if device.serial and not found.done():
                found.set_result(device)

        listener: EarnEP1Listener | None = self.hass.data.get(DOMAIN)

        if listener is not None:
            # Shared listener running — temporarily register this host
            listener.register(host, on_update)
            try:
                async with asyncio.timeout(VALIDATION_TIMEOUT):
                    return await found
            except TimeoutError:
                return None
            finally:
                listener.unregister(host)
        else:
            # No shared listener — create a temporary one
            temp_listener = EarnEP1Listener(port=DEFAULT_PORT)
            temp_listener.register(host, on_update)
            await temp_listener.start()
            try:
                async with asyncio.timeout(VALIDATION_TIMEOUT):
                    return await found
            except TimeoutError:
                return None
            finally:
                await temp_listener.stop()

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
            data={CONF_HOST: host, "serial": device.serial},
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
                return self.async_create_entry(
                    title=f"EARN-E P1 ({device.host})",
                    data={CONF_HOST: device.host, "serial": device.serial},
                )

            # Discovery didn't get serial — validate to obtain it
            try:
                validated = await self._async_validate_host(device.host)
            except OSError:
                validated = None

            if validated is None:
                return self.async_abort(reason="cannot_connect")

            await self.async_set_unique_id(validated.serial)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"EARN-E P1 ({validated.host})",
                data={CONF_HOST: validated.host, "serial": validated.serial},
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": device.host},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_HOST,
                            default=self._get_reconfigure_entry().data[CONF_HOST],
                        ): str,
                    }
                ),
            )

        errors: dict[str, str] = {}
        host = user_input[CONF_HOST]
        entry = self._get_reconfigure_entry()
        serial: str | None = None

        # Only validate if the host changed (same host is already proven)
        if host != entry.data[CONF_HOST]:
            try:
                device = await self._async_validate_host(host)
                if device:
                    serial = device.serial
            except OSError:
                pass
            except Exception:
                _LOGGER.exception("Unexpected error during reconfigure validation")
                errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=host): str,
                    }
                ),
                errors=errors,
            )

        # Preserve existing serial if we couldn't get a new one
        if serial is None:
            serial = entry.data.get("serial")

        if serial is None:
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=host): str,
                    }
                ),
                errors=errors,
            )

        for other in self._async_current_entries(include_ignore=True):
            if other.entry_id != entry.entry_id and other.unique_id == serial:
                return self.async_abort(reason="already_configured")

        return self.async_update_reload_and_abort(
            entry,
            data_updates={CONF_HOST: host, "serial": serial},
            unique_id=serial,
        )
