"""The Synology DSM component."""
from __future__ import annotations

import logging
from typing import Final

from synology_dsm.exceptions import SynologyDSMException
import voluptuous as vol
from wakeonlan import send_magic_packet

from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import async_get

from .common import SynoApi
from .const import (
    DOMAIN,
    SERVICE_POWERON,
    SERVICE_REBOOT,
    SERVICE_SHUTDOWN,
    SERVICES,
    SYNO_API,
    SYSTEM_LOADED,
)

LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.device_id,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Service handler setup."""

    def _send_wol(mac: str, ip_address: str) -> None:
        """Send magic packet to ip and broadcast."""
        send_magic_packet(mac, ip_address=ip_address)
        send_magic_packet(mac)

    async def service_handler(call: ServiceCall) -> None:
        """Handle service call."""
        dev_reg = async_get(hass)
        device_id = call.data[CONF_DEVICE_ID]
        serial = None
        device_ip_macs: set[tuple[str, str]] = set()
        if device := dev_reg.async_get(device_id):
            for entry_id in device.config_entries:
                entry = hass.config_entries.async_get_entry(entry_id)
                if entry and entry.domain == DOMAIN:
                    serial = entry.unique_id
                    device_ip_macs.update(
                        [
                            (entry.data[CONF_HOST], mac)
                            for mac in entry.data.get(CONF_MAC, [])
                        ]
                    )

        if not serial:
            LOGGER.error(
                "Error during service call %s - no suitable device found", call.service
            )
            return

        if call.service in [SERVICE_REBOOT, SERVICE_SHUTDOWN]:
            dsm_device = hass.data[DOMAIN].get(serial)
            if not dsm_device:
                LOGGER.error("DSM with specified serial %s not found", serial)
                return
            LOGGER.debug("%s DSM with serial %s", call.service, serial)
            dsm_api: SynoApi = dsm_device[SYNO_API]
            try:
                if call.service == SERVICE_REBOOT:
                    await dsm_api.async_reboot()
                elif call.service == SERVICE_SHUTDOWN:
                    await dsm_api.async_shutdown()
                dsm_device[SYSTEM_LOADED] = False
            except SynologyDSMException as ex:
                LOGGER.error(
                    "%s of DSM with serial %s not possible, because of %s",
                    call.service,
                    serial,
                    ex,
                )
                return
        elif call.service == SERVICE_POWERON:
            for ip_mac in device_ip_macs:
                LOGGER.debug(
                    "Send magic packet to DSM at %s with mac %s", ip_mac[0], ip_mac[1]
                )
                await hass.async_add_executor_job(_send_wol, ip_mac[1], ip_mac[0])

    for service in SERVICES:
        hass.services.async_register(
            DOMAIN, service, service_handler, schema=SERVICE_SCHEMA
        )
