"""The Forecast.Solar integration."""

from types import MappingProxyType

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event

from .const import (
    CONF_AZIMUTH,
    CONF_AZIMUTH_SENSOR,
    CONF_DAMPING,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_DECLINATION_SENSOR,
    CONF_MODULES_POWER,
    DEFAULT_AZIMUTH,
    DEFAULT_DAMPING,
    DEFAULT_DECLINATION,
    DEFAULT_MODULES_POWER,
    DOMAIN,
    SUBENTRY_TYPE_PLANE,
)
from .coordinator import ForecastSolarConfigEntry, ForecastSolarDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_migrate_entry(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> bool:
    """Migrate old config entry."""

    if entry.version == 1:
        new_options = entry.options.copy()
        new_options |= {
            CONF_MODULES_POWER: new_options.pop("modules power"),
            CONF_DAMPING_MORNING: new_options.get(CONF_DAMPING, DEFAULT_DAMPING),
            CONF_DAMPING_EVENING: new_options.pop(CONF_DAMPING, DEFAULT_DAMPING),
        }

        hass.config_entries.async_update_entry(
            entry, data=entry.data, options=new_options, version=2
        )

    if entry.version == 2:
        # Migrate the main plane from options to a subentry
        declination = entry.options.get(CONF_DECLINATION, DEFAULT_DECLINATION)
        azimuth = entry.options.get(CONF_AZIMUTH, DEFAULT_AZIMUTH)
        modules_power = entry.options.get(CONF_MODULES_POWER, DEFAULT_MODULES_POWER)

        subentry = ConfigSubentry(
            data=MappingProxyType(
                {
                    CONF_DECLINATION: declination,
                    CONF_AZIMUTH: azimuth,
                    CONF_MODULES_POWER: modules_power,
                }
            ),
            subentry_type=SUBENTRY_TYPE_PLANE,
            title=f"{declination}° / {azimuth}° / {modules_power}W",
            unique_id=None,
        )
        hass.config_entries.async_add_subentry(entry, subentry)

        new_options = dict(entry.options)
        new_options.pop(CONF_DECLINATION, None)
        new_options.pop(CONF_AZIMUTH, None)
        new_options.pop(CONF_MODULES_POWER, None)

        hass.config_entries.async_update_entry(entry, options=new_options, version=3)

    return True


@callback
def _async_track_sensor_renames(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> CALLBACK_TYPE:
    """Keep a plane's sensor reference pointing at the sensor when it is renamed."""
    sensor_keys = (CONF_DECLINATION_SENSOR, CONF_AZIMUTH_SENSOR)
    entity_ids = [
        entity_id
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)
        for key in sensor_keys
        if (entity_id := subentry.data.get(key))
    ]

    @callback
    def _async_sensor_renamed(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        if event.data["action"] != "update":
            return
        old_entity_id = event.data["changes"].get("entity_id")
        if old_entity_id is None:
            return

        new_entity_id = event.data["entity_id"]
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE):
            renamed = {
                key: new_entity_id
                for key in sensor_keys
                if subentry.data.get(key) == old_entity_id
            }
            if renamed:
                hass.config_entries.async_update_subentry(
                    entry, subentry, data=subentry.data | renamed
                )

    return async_track_entity_registry_updated_event(
        hass, entity_ids, _async_sensor_renamed
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> bool:
    """Set up Forecast.Solar from a config entry."""
    plane_subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)
    if not plane_subentries:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_plane",
        )

    if len(plane_subentries) > 1 and not entry.options.get(CONF_API_KEY):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="api_key_required",
        )

    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(_async_track_sensor_renames(hass, entry))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> None:
    """Handle config entry updates (options or subentry changes)."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
