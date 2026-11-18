"""Config flow for Govee light local."""

import asyncio
from ipaddress import AddressValueError, IPv4Address
import logging
from typing import Any, override

from govee_local_api import GoveeController
import probatio

from homeassistant.components import onboarding
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from . import async_get_listening_addresses
from .const import (
    CONF_DEVICE_IP,
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from .coordinator import async_cleanup_controller, log_bound_addresses

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""

    listening_addresses = await async_get_listening_addresses(hass)
    if not listening_addresses:
        _LOGGER.debug("No enabled IPv4 addresses to listen on")
        return False

    controller: GoveeController = GoveeController(
        loop=hass.loop,
        logger=_LOGGER,
        listening_addresses=listening_addresses,
        broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
        broadcast_port=CONF_TARGET_PORT_DEFAULT,
        listening_port=CONF_LISTENING_PORT_DEFAULT,
        discovery_enabled=True,
        discovery_interval=1,
        update_enabled=False,
    )

    try:
        _LOGGER.debug("Starting discovery on %s", listening_addresses)
        # Probe through whichever adapters bind; only a total failure aborts.
        await controller.start(require_all=False)
    except OSError as ex:
        _LOGGER.error("Start failed, errno: %d", ex.errno)
        return False

    log_bound_addresses(controller)

    try:
        async with asyncio.timeout(delay=DISCOVERY_TIMEOUT):
            while not controller.devices:
                await asyncio.sleep(delay=1)
    except TimeoutError:
        _LOGGER.debug("No devices found")
    finally:
        # cleanup() clears the device registry, so count before tearing down.
        devices_count = len(controller.devices)
        await async_cleanup_controller(controller)

    return devices_count > 0


class GoveeConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee light local."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        await self.async_set_unique_id(DOMAIN)

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup."""
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            if not await _async_has_devices(self.hass):
                return self.async_abort(reason="no_devices_found")
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="confirm", last_step=True)

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by this integration."""
        return {SUBENTRY_TYPE_DEVICE: GoveeDeviceSubentryFlowHandler}


class GoveeDeviceSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding a Govee light by IP address."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a device by IP address."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            user_ip = user_input[CONF_DEVICE_IP]
            try:
                IPv4Address(user_ip)
            except AddressValueError:
                errors["base"] = "invalid_ip"
                placeholders["ip"] = user_ip
            else:
                if any(
                    subentry.unique_id == user_ip
                    for subentry in self._get_entry().subentries.values()
                ):
                    errors["base"] = "already_configured"
                    placeholders["ip"] = user_ip
                else:
                    return self.async_create_entry(
                        title=user_ip,
                        data={CONF_DEVICE_IP: user_ip},
                        unique_id=user_ip,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema({probatio.Required(CONF_DEVICE_IP): cv.string}),
            errors=errors,
            description_placeholders=placeholders,
            last_step=True,
        )
