"""The Forecast.Solar integration."""

from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.event import (
    EventStateChangedData,
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
from .coordinator import ForecastSolarConfigEntry, ForecastSolarDataUpdateCoordinator
from .plane import SensorUpdateFailed, plane_title
from .services import async_setup_services

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Forecast.Solar integration."""
    async_setup_services(hass)
    _async_track_sensor_renames(hass)
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
def _async_track_sensor_states(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> CALLBACK_TYPE:
    """Follow a plane sensor's name, and retry an update that failed on it."""
    refreshing = False

    async def _async_refresh() -> None:
        nonlocal refreshing
        refreshing = True
        try:
            await entry.runtime_data.async_request_refresh()
        finally:
            refreshing = False

    @callback
    def _async_sensor_changed(event: Event[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        # A plane titled after its sensor follows the sensor's name. A renamed sensor
        # has no state under its new entity ID yet, so its first state titles it too.
        if new_state and (old_state is None or old_state.name != new_state.name):
            entity_id = event.data["entity_id"]
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE):
                if entity_id in (subentry.data.get(key) for key in _SENSOR_KEYS):
                    hass.config_entries.async_update_subentry(
                        entry, subentry, title=plane_title(hass, subentry.data)
                    )

        coordinator = entry.runtime_data
        # Only sensor failures retry early; healthy updates and API failures keep
        # their schedule, so a fast-changing sensor can't spend the rate limit.
        # A refresh in flight still reports the failure it is retrying, so without
        # this guard every further change would queue another API call.
        if (
            not refreshing
            and not coordinator.last_update_success
            and isinstance(coordinator.last_exception, SensorUpdateFailed)
        ):
            entry.async_create_task(hass, _async_refresh())

    return async_track_state_change_event(
        hass, _sensor_entity_ids(entry), _async_sensor_changed
    )


@callback
def _async_track_sensor_renames(hass: HomeAssistant) -> None:
    """Keep the planes' sensor references pointing at their sensors when renamed.

    Tracked for the integration, not per entry: an entry whose sensor is unreadable
    sits in SETUP_RETRY with its own listeners torn down, and a rename during that
    window is what leaves it pointing at an entity ID that never comes back.
    """

    @callback
    def _async_sensor_renamed(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        if event.data["action"] != "update":
            return
        old_entity_id = event.data["changes"].get("entity_id")
        if old_entity_id is None:
            return

        new_entity_id = event.data["entity_id"]
        for entry in hass.config_entries.async_entries(DOMAIN):
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE):
                renamed = {
                    key: new_entity_id
                    for key in _SENSOR_KEYS
                    if subentry.data.get(key) == old_entity_id
                }
                if renamed:
                    data = subentry.data | renamed
                    hass.config_entries.async_update_subentry(
                        entry, subentry, data=data, title=plane_title(hass, data)
                    )

    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _async_sensor_renamed)


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

    # A rename resolves its plane's title only once the sensor has a state again.
    for subentry in plane_subentries:
        hass.config_entries.async_update_subentry(
            entry, subentry, title=plane_title(hass, subentry.data)
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(_async_reload_on_forecast_change(hass, entry))
    entry.async_on_unload(_async_track_sensor_states(hass, entry))

    return True


def _forecast_inputs(entry: ForecastSolarConfigEntry) -> tuple[Any, ...]:
    """Return the entry values the forecast is built from."""
    return (
        dict(entry.data),
        dict(entry.options),
        [
            dict(subentry.data)
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)
        ],
    )


@callback
def _async_reload_on_forecast_change(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> CALLBACK_TYPE:
    """Reload on option and plane changes, but not on a title-only update."""
    inputs = _forecast_inputs(entry)
    reloading = False

    async def _async_reload() -> None:
        nonlocal reloading
        try:
            await hass.config_entries.async_reload(entry.entry_id)
        finally:
            # A reload that failed to unload leaves this listener in place.
            reloading = False

    async def _async_entry_updated(
        hass: HomeAssistant, entry: ForecastSolarConfigEntry
    ) -> None:
        nonlocal reloading
        # Renaming a sensor updates every plane reading it; one reload covers them all.
        if not reloading and _forecast_inputs(entry) != inputs:
            reloading = True
            hass.async_create_task(
                _async_reload(), f"forecast_solar reload {entry.entry_id}"
            )

    return entry.add_update_listener(_async_entry_updated)


async def async_unload_entry(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
