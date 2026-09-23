"""Support for Hydrawise cloud."""

from collections.abc import Iterable

from pydrawise import Controller, auth, hybrid

from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr

from .const import APP_ID, DOMAIN, MANUFACTURER
from .coordinator import (
    HydrawiseConfigEntry,
    HydrawiseMainDataUpdateCoordinator,
    HydrawiseUpdateCoordinators,
    HydrawiseWaterUseDataUpdateCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VALVE,
]

_REQUIRED_AUTH_KEYS = (CONF_USERNAME, CONF_PASSWORD, CONF_API_KEY)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: HydrawiseConfigEntry
) -> bool:
    """Set up Hydrawise from a config entry."""
    if any(k not in config_entry.data for k in _REQUIRED_AUTH_KEYS):
        # If we are missing any required authentication keys, trigger a reauth flow.
        raise ConfigEntryAuthFailed

    hydrawise = hybrid.HybridClient(
        auth.HybridAuth(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            config_entry.data[CONF_API_KEY],
        ),
        app_id=APP_ID,
    )

    main_coordinator = HydrawiseMainDataUpdateCoordinator(hass, config_entry, hydrawise)
    await main_coordinator.async_config_entry_first_refresh()
    water_use_coordinator = HydrawiseWaterUseDataUpdateCoordinator(
        hass, config_entry, hydrawise, main_coordinator
    )

    device_registry = dr.async_get(hass)

    @callback
    def _async_register_controller_devices(controllers: Iterable[Controller]) -> None:
        """Register controller devices so children can resolve via_device_id.

        Runs as the first new-controller callback so via_device parents are
        registered before the new-zone callbacks construct zone entities that
        resolve their via_device_id. Registration must not run before
        _add_remove_zones computes the previous controllers, or newly discovered
        controllers would be treated as already-known and their controller-level
        entities would never be added.
        """
        for controller in controllers:
            device_registry.async_get_or_create(
                config_entry_id=config_entry.entry_id,
                identifiers={(DOMAIN, str(controller.id))},
                manufacturer=MANUFACTURER,
                model=controller.hardware.model.description,
                name=controller.name,
            )

    # Register the controllers known at setup before the platforms construct
    # their entities.
    _async_register_controller_devices(main_coordinator.data.controllers.values())
    main_coordinator.new_controllers_callbacks.append(
        _async_register_controller_devices
    )

    # async_track_zones is registered first on water_use_coordinator,
    # so the water-use coordinator's data is in sync before
    # callbacks below construct entities for newly added zones.
    water_use_coordinator.async_track_zones()
    main_coordinator.async_track_zones()
    await water_use_coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = HydrawiseUpdateCoordinators(
        main=main_coordinator,
        water_use=water_use_coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HydrawiseConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
