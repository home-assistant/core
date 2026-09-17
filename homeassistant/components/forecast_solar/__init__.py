"""The Forecast.Solar integration."""

from types import MappingProxyType

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import ConfigType

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
from .coordinator import (
    ForecastSolarConfigEntry,
    ForecastSolarDataUpdateCoordinator,
    SensorUpdateFailed,
)
from .services import async_setup_services

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Forecast.Solar integration."""
    async_setup_services(hass)
    return True


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


_SENSOR_KEYS = (CONF_DECLINATION_SENSOR, CONF_AZIMUTH_SENSOR)


def _sensor_entity_ids(entry: ForecastSolarConfigEntry) -> set[str]:
    """Return the entity IDs of every sensor the entry's planes read."""
    # Deduplicated: the event trackers call the listener once per listed ID.
    return {
        entity_id
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)
        for key in _SENSOR_KEYS
        if (entity_id := subentry.data.get(key))
    }


@callback
def _async_refresh_on_sensor_change(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> CALLBACK_TYPE:
    """Retry an update that failed on a sensor as soon as a plane sensor changes."""

    @callback
    def _async_sensor_changed(event: Event[EventStateChangedData]) -> None:
        coordinator = entry.runtime_data
        # Only sensor failures retry early; healthy updates and API failures keep
        # their schedule, so a fast-changing sensor can't spend the rate limit.
        if not coordinator.last_update_success and isinstance(
            coordinator.last_exception, SensorUpdateFailed
        ):
            entry.async_create_task(hass, coordinator.async_request_refresh())

    return async_track_state_change_event(
        hass, _sensor_entity_ids(entry), _async_sensor_changed
    )


@callback
def _async_track_sensor_renames(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> CALLBACK_TYPE:
    """Keep a plane's sensor reference pointing at the sensor when it is renamed."""

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
                for key in _SENSOR_KEYS
                if subentry.data.get(key) == old_entity_id
            }
            if renamed:
                # Friendly names survive a rename; only entity ID labels go stale.
                title = subentry.title.replace(
                    f"{old_entity_id} (sensor)", f"{new_entity_id} (sensor)"
                )
                hass.config_entries.async_update_subentry(
                    entry, subentry, data=subentry.data | renamed, title=title
                )

    return async_track_entity_registry_updated_event(
        hass, _sensor_entity_ids(entry), _async_sensor_renamed
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
    entry.async_on_unload(_async_refresh_on_sensor_change(hass, entry))

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
