"""Services for the Portainer integration."""

from datetime import timedelta

from pyportainer import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .coordinator import PortainerConfigEntry

ATTR_DATE_UNTIL = "until"
ATTR_DANGLING = "dangling"
ATTR_TIMEOUT = "timeout"
ATTR_PULL_IMAGE = "pull_image"
ATTR_CONTAINER_DEVICE_ID = "container_device_id"

SERVICE_PRUNE_IMAGES = "prune_images"
SERVICE_PRUNE_IMAGES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_DATE_UNTIL): vol.All(
            cv.time_period, vol.Range(min=timedelta(minutes=1))
        ),
        vol.Optional(ATTR_DANGLING): cv.boolean,
    },
)

SERVICE_RECREATE_CONTAINER = "recreate_container"
SERVICE_RECREATE_CONTAINER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_CONTAINER_DEVICE_ID): cv.string,
        vol.Optional(ATTR_TIMEOUT): vol.All(
            cv.time_period, vol.Range(min=timedelta(minutes=1))
        ),
        vol.Optional(ATTR_PULL_IMAGE): cv.boolean,
    }
)


async def _extract_config_entry(service_call: ServiceCall) -> PortainerConfigEntry:
    """Extract config entry from the service call."""
    target_entry_ids = await async_extract_config_entry_ids(service_call)
    target_entries: list[PortainerConfigEntry] = [
        loaded_entry
        for loaded_entry in service_call.hass.config_entries.async_loaded_entries(
            DOMAIN
        )
        if loaded_entry.entry_id in target_entry_ids
    ]
    if not target_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target",
        )
    return target_entries[0]


async def _get_endpoint_id(
    call: ServiceCall,
    config_entry: PortainerConfigEntry,
) -> int:
    """Get endpoint data from device ID."""
    device_reg = dr.async_get(call.hass)
    device_id = call.data[ATTR_DEVICE_ID]
    device = device_reg.async_get(device_id)
    assert device
    coordinator = config_entry.runtime_data

    endpoint_data = None
    for data in coordinator.data.values():
        if (
            DOMAIN,
            f"{config_entry.entry_id}_{data.endpoint.id}",
        ) in device.identifiers:
            endpoint_data = data
            break

    assert endpoint_data
    return endpoint_data.endpoint.id


async def _get_container_id(
    call: ServiceCall,
    config_entry: PortainerConfigEntry,
) -> str:
    """Get container ID from device ID."""
    device_reg = dr.async_get(call.hass)
    device_id = call.data[ATTR_CONTAINER_DEVICE_ID]
    device = device_reg.async_get(device_id)
    assert device
    coordinator = config_entry.runtime_data

    con_data = None
    for data in coordinator.data.values():
        for container_name, container_data in data.containers.items():
            if (
                DOMAIN,
                f"{config_entry.entry_id}_{data.endpoint.id}_{container_name}",
            ) in device.identifiers:
                con_data = container_data
                break

    assert con_data
    return con_data.container.id


async def prune_images(call: ServiceCall) -> None:
    """Prune unused images in Portainer, with more controls."""
    config_entry = await _extract_config_entry(call)
    coordinator = config_entry.runtime_data
    endpoint_id = await _get_endpoint_id(call, config_entry)

    try:
        await coordinator.portainer.images_prune(
            endpoint_id=endpoint_id,
            until=call.data.get(ATTR_DATE_UNTIL),
            dangling=call.data.get(ATTR_DANGLING, False),
        )
    except PortainerAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth_no_details",
        ) from err
    except PortainerConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect_no_details",
        ) from err
    except PortainerTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect_no_details",
        ) from err


async def recreate_container(call: ServiceCall) -> None:
    """Recreate a container in Portainer, with more controls."""
    config_entry = await _extract_config_entry(call)
    coordinator = config_entry.runtime_data
    timeout: timedelta | None = call.data.get(ATTR_TIMEOUT)

    try:
        await coordinator.portainer.container_recreate(
            endpoint_id=await _get_endpoint_id(call, config_entry),
            container_id=await _get_container_id(call, config_entry),
            **({"timeout": timeout} if timeout is not None else {}),
            pull_image=call.data.get(ATTR_PULL_IMAGE, False),
        )
    except PortainerAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth_no_details",
        ) from err
    except PortainerConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect_no_details",
        ) from err
    except PortainerTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect_no_details",
        ) from err


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_PRUNE_IMAGES,
        prune_images,
        SERVICE_PRUNE_IMAGES_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RECREATE_CONTAINER,
        recreate_container,
        SERVICE_RECREATE_CONTAINER_SCHEMA,
    )
