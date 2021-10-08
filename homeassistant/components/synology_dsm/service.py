"""The Synology DSM component."""
from __future__ import annotations

import logging

from synology_dsm.exceptions import SynologyDSMException
from wakeonlan import send_magic_packet

from homeassistant.const import ATTR_AREA_ID, ATTR_DEVICE_ID, CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    async_entries_for_area,
    async_get_registry,
)

from .const import (
    DOMAIN,
    SERVICE_POWERON,
    SERVICE_REBOOT,
    SERVICE_SHUTDOWN,
    SERVICES,
    SYNO_API,
    SYSTEM_LOADED,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Service handler setup."""

    def _send_wol(mac: str, ip: str) -> None:
        """Send magic packet to ip and broadcast."""
        send_magic_packet(mac, ip_address=ip)
        send_magic_packet(mac)

    async def service_handler(call: ServiceCall) -> None:
        """Handle service call."""
        dev_reg = await async_get_registry(hass)
        devices: list[DeviceEntry] = []
        device_serials: set[str] = set()
        device_ip_macs: set[tuple[str, str]] = set()

        if area_ids := call.data.get(ATTR_AREA_ID):
            for area_id in area_ids:
                devices.extend(
                    [
                        device
                        for device in async_entries_for_area(dev_reg, area_id)
                        if DOMAIN in [x[0] for x in device.identifiers]
                    ]
                )

        if device_ids := call.data.get(ATTR_DEVICE_ID):
            for device_id in device_ids:
                if dev := dev_reg.async_get(device_id):
                    devices.append(dev)

        for device in devices:
            if via_device_id := device.via_device_id:
                if dev := dev_reg.async_get(via_device_id):
                    device = dev
            for identifier in device.identifiers:
                if DOMAIN not in identifier[0]:
                    continue
                device_serials.add(identifier[1])
                for config_entry in device.config_entries:
                    if entry := hass.config_entries.async_get_entry(config_entry):
                        device_ip_macs.update(
                            [
                                (entry.data[CONF_HOST], mac)
                                for mac in entry.data.get(CONF_MAC, [])
                            ]
                        )

        if call.service in [SERVICE_REBOOT, SERVICE_SHUTDOWN]:
            dsm_devices = hass.data[DOMAIN]
            for serial in device_serials:
                dsm_device = dsm_devices.get(serial)
                if not dsm_device:
                    _LOGGER.error("DSM with specified serial %s not found", serial)
                    continue
                _LOGGER.debug("%s DSM with serial %s", call.service, serial)
                dsm_api = dsm_device[SYNO_API]
                try:
                    if call.service == SERVICE_REBOOT:
                        await dsm_api.async_reboot()
                    elif call.service == SERVICE_SHUTDOWN:
                        await dsm_api.async_shutdown()
                    dsm_device[SYSTEM_LOADED] = False
                except SynologyDSMException as ex:
                    _LOGGER.error(
                        "%s of DSM with serial %s not possible, because of %s",
                        call.service,
                        serial,
                        ex,
                    )

        elif call.service == SERVICE_POWERON:
            for ip_mac in device_ip_macs:
                _LOGGER.debug(
                    "Send magic packet to DSM at %s with mac %s", ip_mac[0], ip_mac[1]
                )
                await hass.async_add_executor_job(_send_wol, ip_mac[1], ip_mac[0])

    for service in SERVICES:
        hass.services.async_register(DOMAIN, service, service_handler)
