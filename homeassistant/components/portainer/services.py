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

    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target",
        )

    coordinator = config_entry.runtime_data

    for data in coordinator.data.values():
        if (
            DOMAIN,
            f"{config_entry.entry_id}_{data.endpoint.id}",
        ) in device.identifiers:
            return data.endpoint.id

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_target",
    )


async def _get_container_and_endpoint_ids(
    call: ServiceCall,
) -> tuple[PortainerConfigEntry, int, str]:
    """Get config entry, endpoint ID and container ID from the container device ID."""
    device_reg = dr.async_get(call.hass)
    device = device_reg.async_get(call.data[ATTR_CONTAINER_DEVICE_ID])

    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target",
        )

    config_entry: PortainerConfigEntry | None = None
    for loaded_entry in call.hass.config_entries.async_loaded_entries(DOMAIN):
        if loaded_entry.entry_id in device.config_entries:
            config_entry = loaded_entry
            break

    if config_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target",
        )

    coordinator = config_entry.runtime_data
    for data in coordinator.data.values():
        for container_name, container_data in data.containers.items():
            if (
                DOMAIN,
                f"{config_entry.entry_id}_{data.endpoint.id}_{container_name}",
            ) in device.identifiers:
                return config_entry, data.endpoint.id, container_data.container.id

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_target",
    )


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
    config_entry, endpoint_id, container_id = await _get_container_and_endpoint_ids(
        call
    )
    coordinator = config_entry.runtime_data
    timeout: timedelta | None = call.data.get(ATTR_TIMEOUT)

    try:
        await coordinator.portainer.container_recreate(
            endpoint_id=endpoint_id,
            container_id=container_id,
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

    await coordinator.async_request_refresh()


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
