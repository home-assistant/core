"""Platform for the Daikin AC."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.helpers.device_registry import AnyDeviceEntry, ChildDeviceEntry

from .const import DOMAIN
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .utils import account_device_identifier, account_identifier

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.WATER_HEATER,
]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DaikinOnectaConfigEntry
) -> None:
    """Establish connection with Daikin."""
    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, config_entry
            )
        )
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, implementation)
    config_entry.runtime_data = coordinator

    await config_entry.runtime_data.async_config_entry_first_refresh()
    coordinator.async_register_devices()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DaikinOnectaConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)


def _daikin_device_identifier(device_entry: AnyDeviceEntry) -> str | None:
    """Return the first Daikin identifier from a registry device."""
    return next(
        (
            identifier
            for domain, identifier in device_entry.identifiers
            if domain == DOMAIN
        ),
        None,
    )


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    device_entry: AnyDeviceEntry,
) -> bool:
    """Allow removal of empty child devices or devices absent from the account."""
    if config_entry.state is not ConfigEntryState.LOADED:
        return False
    gateway_id = _daikin_device_identifier(device_entry)
    account_id = account_identifier(config_entry)
    if gateway_id is None or gateway_id == account_device_identifier(account_id):
        return False

    coordinator = config_entry.runtime_data
    parent_device_id = (
        device_entry.parent_device_id
        if isinstance(device_entry, ChildDeviceEntry)
        else device_entry.via_device_id
    )
    if parent_device_id is not None:
        parent_device = dr.async_get(hass).async_get(
            parent_device_id, include_child_devices=False
        )
        if parent_device is None:
            return False
        parent_gateway_id = _daikin_device_identifier(parent_device)
        if parent_gateway_id is None:
            return False
        child_prefix = f"{parent_gateway_id}_"
        if not gateway_id.startswith(child_prefix):
            return False
        embedded_id = gateway_id[len(child_prefix) :]
        if not er.async_entries_for_device(
            er.async_get(hass), device_entry.id, include_disabled_entities=True
        ):
            return coordinator.last_update_success
        return await _async_gateway_or_point_confirmed_absent(
            coordinator, parent_gateway_id, embedded_id
        )

    return await _async_gateway_or_point_confirmed_absent(coordinator, gateway_id)


async def _async_gateway_or_point_confirmed_absent(
    coordinator: OnectaDataUpdateCoordinator,
    gateway_id: str,
    embedded_id: str | None = None,
) -> bool:
    """Check current data and Sites before allowing device removal."""
    if not coordinator.last_update_success:
        return False

    if (
        result := _cached_device_removal_result(coordinator, gateway_id, embedded_id)
    ) is not None:
        return result

    site_lookup = await coordinator.async_get_site_lookup(start_reauth=True)
    if (
        site_lookup.gateway_membership(gateway_id) is not False
        or not coordinator.last_update_success
    ):
        return False

    # Polling may restore the gateway while the Sites request is in flight.
    if (
        result := _cached_device_removal_result(coordinator, gateway_id, embedded_id)
    ) is not None:
        return result
    return True


def _cached_device_removal_result(
    coordinator: OnectaDataUpdateCoordinator,
    gateway_id: str,
    embedded_id: str | None,
) -> bool | None:
    """Return a removal result when the gateway is present in the latest poll."""
    device = (coordinator.data or {}).get(gateway_id)
    if device is None or not device.present_in_cloud:
        return None
    if embedded_id is not None and (
        not device.available or not device.device.management_points
    ):
        return False
    return _management_point_is_absent(device, embedded_id)


def _management_point_is_absent(
    device: DaikinOnectaDevice, embedded_id: str | None
) -> bool:
    """Return whether the requested point is absent from a present gateway."""
    return embedded_id is not None and device.management_point(embedded_id) is None
