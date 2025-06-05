"""The Synology DSM component."""

from __future__ import annotations

import logging
from typing import cast

from synology_dsm.exceptions import SynologyDSMException

from homeassistant.core import HomeAssistant, ServiceCall

from .const import CONF_SERIAL, DOMAIN, SERVICE_REBOOT, SERVICE_SHUTDOWN, SERVICES
from .coordinator import SynologyDSMConfigEntry

LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Service handler setup."""

    async def service_handler(call: ServiceCall) -> None:
        """Handle service call."""
        serial: str | None = call.data.get(CONF_SERIAL)
        entries: list[SynologyDSMConfigEntry] = (
            hass.config_entries.async_loaded_entries(DOMAIN)
        )
        dsm_devices = {
            cast(str, entry.unique_id): entry.runtime_data for entry in entries
        }

        if serial:
            entry: SynologyDSMConfigEntry | None = (
                hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, serial)
            )
            assert entry
            dsm_device = entry.runtime_data
        elif len(dsm_devices) == 1:
            dsm_device = next(iter(dsm_devices.values()))
            serial = next(iter(dsm_devices))
        else:
            LOGGER.error(
                "More than one DSM configured, must specify one of serials %s",
                sorted(dsm_devices),
            )
            return

        if not dsm_device:
            LOGGER.error("DSM with specified serial %s not found", serial)
            return

        if call.service in [SERVICE_REBOOT, SERVICE_SHUTDOWN]:
            if serial not in dsm_devices:
                LOGGER.error("DSM with specified serial %s not found", serial)
                return
            LOGGER.debug("%s DSM with serial %s", call.service, serial)
            LOGGER.warning(
                (
                    "The %s service is deprecated and will be removed in future"
                    " release. Please use the corresponding button entity"
                ),
                call.service,
            )
            dsm_device = dsm_devices[serial]
            dsm_api = dsm_device.api
            try:
                await getattr(dsm_api, f"async_{call.service}")()
            except SynologyDSMException as ex:
                LOGGER.error(
                    "%s of DSM with serial %s not possible, because of %s",
                    call.service,
                    serial,
                    ex,
                )
                return

    for service in SERVICES:
        hass.services.async_register(DOMAIN, service, service_handler)
