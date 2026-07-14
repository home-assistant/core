"""Services for the Portainer integration."""

from datetime import timedelta

from pyportainer import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)

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


@callback
def _async_get_device(call: ServiceCall, device_id: str) -> dr.DeviceEntry:
    """Get a device entry from a device ID."""
    device_reg = dr.async_get(call.hass)
    if (device := device_reg.async_get(device_id)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target",
        )
    return device


@callback
def _async_get_entry_from_device(
    call: ServiceCall, device: dr.DeviceEntry
) -> PortainerConfigEntry:
    """Resolve and validate the Portainer config entry for a device."""
    for entry in call.hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id in device.config_entries:
            return service.async_get_config_entry(call.hass, DOMAIN, entry.entry_id)

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_target",
    )


@callback
def _async_get_endpoint_id(
    device: dr.DeviceEntry,
    config_entry: PortainerConfigEntry,
) -> int:
    """Get the endpoint ID from a device entry."""
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


@callback
def _async_get_container_and_endpoint_ids(
    device: dr.DeviceEntry,
    config_entry: PortainerConfigEntry,
) -> tuple[int, str]:
    """Get the endpoint ID and container ID from a container device entry."""
    coordinator = config_entry.runtime_data

    for data in coordinator.data.values():
        for container_name, container_data in data.containers.items():
            if (
                DOMAIN,
                f"{config_entry.entry_id}_{data.endpoint.id}_{container_name}",
            ) in device.identifiers:
                return data.endpoint.id, container_data.container.id

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_target",
    )


async def prune_images(call: ServiceCall) -> None:
    """Prune unused images in Portainer, with more controls."""
    device = _async_get_device(call, call.data[ATTR_DEVICE_ID])
    config_entry = _async_get_entry_from_device(call, device)
    coordinator = config_entry.runtime_data
    endpoint_id = _async_get_endpoint_id(device, config_entry)

    try:
        await coordinator.portainer.images_prune(
            endpoint_id=endpoint_id,
            until=call.data.get(ATTR_DATE_UNTIL),
            dangling=call.data.get(ATTR_DANGLING, False),
        )
    except PortainerAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except PortainerConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except PortainerTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
        ) from err


async def recreate_container(call: ServiceCall) -> None:
    """Recreate a container in Portainer, with more controls."""
    device = _async_get_device(call, call.data[ATTR_CONTAINER_DEVICE_ID])
    config_entry = _async_get_entry_from_device(call, device)
    coordinator = config_entry.runtime_data
    endpoint_id, container_id = _async_get_container_and_endpoint_ids(
        device, config_entry
    )
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
            translation_key="invalid_auth",
        ) from err
    except PortainerConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except PortainerTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
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
