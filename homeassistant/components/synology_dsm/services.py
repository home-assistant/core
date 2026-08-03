"""The Synology DSM component."""

import logging
from typing import cast

from synology_dsm.exceptions import SynologyDSMException

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_SERIAL, DOMAIN, SERVICE_REBOOT, SERVICE_SHUTDOWN, SERVICES
from .coordinator import SynologyDSMConfigEntry

LOGGER = logging.getLogger(__name__)


async def _service_handler(call: ServiceCall) -> None:
    """Handle service call."""
    serial: str | None = call.data.get(CONF_SERIAL)
    entries: list[SynologyDSMConfigEntry] = (
        call.hass.config_entries.async_loaded_entries(DOMAIN)
    )
    dsm_devices = {cast(str, entry.unique_id): entry.runtime_data for entry in entries}

    if serial:
        entry: SynologyDSMConfigEntry | None = (
            call.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, serial)
        )
        if not entry:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="serial_not_found",
                translation_placeholders={"serial": serial},
            )
        dsm_device = entry.runtime_data
    elif len(dsm_devices) == 1:
        dsm_device = next(iter(dsm_devices.values()))
        serial = next(iter(dsm_devices))
    else:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="missing_serial",
            translation_placeholders={"serials": ", ".join(sorted(dsm_devices))},
        )

    if not dsm_device:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="serial_not_found",
            translation_placeholders={"serial": serial},
        )

    if call.service in [SERVICE_REBOOT, SERVICE_SHUTDOWN]:
        if serial not in dsm_devices:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="serial_not_found",
                translation_placeholders={"serial": serial},
            )
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
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="execution_error",
                translation_placeholders={
                    "action": call.service,
                    "serial": serial,
                    "error": str(ex),
                },
            ) from ex


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Service handler setup."""

    for service in SERVICES:
        hass.services.async_register(DOMAIN, service, _service_handler)
