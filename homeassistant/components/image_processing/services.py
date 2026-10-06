"""Services for the image_processing integration."""

import asyncio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.config_validation import make_entity_service_schema

from .const import DATA_COMPONENT, DOMAIN, SERVICE_SCAN


async def _async_scan_service(service: ServiceCall) -> None:
    """Service handler for scan."""
    image_entities = await service.hass.data[DATA_COMPONENT].async_extract_from_service(
        service
    )

    update_tasks = []
    for entity in image_entities:
        entity.async_set_context(service.context)
        update_tasks.append(asyncio.create_task(entity.async_update_ha_state(True)))

    if update_tasks:
        await asyncio.wait(update_tasks)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the image_processing services."""
    hass.services.async_register(
        DOMAIN, SERVICE_SCAN, _async_scan_service, schema=make_entity_service_schema({})
    )
