"""Config flow for Duosida EV Charger integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import AbortFlow, FlowResult

from duosida_ev import DuosidaCharger, discover_chargers

from .const import CONF_DEVICE_ID, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DuosidaLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Duosida EV Charger."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            if user_input.get("discovery"):
                return await self.async_step_discovery()
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("discovery", default=True): bool,
                }
            ),
        )

    async def async_step_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the discovery step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input["device"]

            for device in self._discovered_devices:
                if device["ip"] == selected:
                    await self.async_set_unique_id(device["device_id"])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"Duosida {device['ip']}",
                        data={
                            CONF_HOST: device["ip"],
                            CONF_PORT: DEFAULT_PORT,
                            CONF_DEVICE_ID: device["device_id"],
                        },
                    )

        _LOGGER.debug("Starting device discovery")
        self._discovered_devices = await self.hass.async_add_executor_job(
            discover_chargers, 5
        )
        _LOGGER.debug("Found %d devices", len(self._discovered_devices))

        if not self._discovered_devices:
            return self.async_show_form(
                step_id="discovery",
                errors={"base": "no_devices_found"},
            )

        devices = {
            device["ip"]: f"{device['ip']} ({device.get('device_id', 'Unknown')})"
            for device in self._discovered_devices
        }

        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(devices),
                }
            ),
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            device_id = user_input.get(CONF_DEVICE_ID)

            try:
                _LOGGER.debug("Testing connection to %s:%s", host, port)

                charger = await self.hass.async_add_executor_job(
                    lambda: DuosidaCharger(
                        host=host,
                        port=port,
                        device_id=device_id or "test",
                        debug=False,
                    )
                )

                connected = await self.hass.async_add_executor_job(charger.connect)

                if not connected:
                    errors["base"] = "cannot_connect"
                else:
                    if not device_id:
                        status = await self.hass.async_add_executor_job(
                            charger.get_status
                        )
                        if status:
                            device_id = charger.device_id
                            _LOGGER.debug("Retrieved device ID: %s", device_id)
                        else:
                            errors["base"] = "cannot_connect"

                    await self.hass.async_add_executor_job(charger.disconnect)

                    if not errors:
                        await self.async_set_unique_id(device_id)
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=f"Duosida {host}",
                            data={
                                CONF_HOST: host,
                                CONF_PORT: port,
                                CONF_DEVICE_ID: device_id,
                            },
                        )

            except AbortFlow:
                raise
            except Exception as e:
                _LOGGER.error("Error connecting to charger: %s", e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_DEVICE_ID): str,
                }
            ),
            errors=errors,
        )
