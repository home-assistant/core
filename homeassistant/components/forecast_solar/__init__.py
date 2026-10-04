"""The Forecast.Solar integration."""

from datetime import timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    EVENT_CORE_CONFIG_UPDATE,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AZIMUTH,
    CONF_DAMPING,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_MODULES_POWER,
    DEFAULT_AZIMUTH,
    DEFAULT_DAMPING,
    DEFAULT_DECLINATION,
    DEFAULT_MODULES_POWER,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_PLANE,
)
from .coordinator import ForecastSolarConfigEntry, ForecastSolarDataUpdateCoordinator
from .plane import SENSOR_KEYS, plane_title
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


@callback
def _async_track_sensor_renames(hass: HomeAssistant) -> None:
    """Keep the planes' sensor references pointing at their sensors when renamed.

    Tracked for the integration, not per entry: an entry whose sensor is unreadable
    sits in SETUP_RETRY with its own listeners torn down, and a rename during that
    window is what leaves it pointing at an entity ID that never comes back.
    """

    @callback
    def _async_is_rename(event_data: er.EventEntityRegistryUpdatedData) -> bool:
        return "old_entity_id" in event_data

    @callback
    def _async_sensor_renamed(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        if TYPE_CHECKING:
            assert event.data["action"] == "update"
        old_entity_id = event.data["old_entity_id"]
        new_entity_id = event.data["entity_id"]
        for entry in hass.config_entries.async_entries(DOMAIN):
            updated = False
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE):
                renamed = {
                    key: new_entity_id
                    for key in SENSOR_KEYS
                    if subentry.data.get(key) == old_entity_id
                }
                if not renamed:
                    continue
                data = subentry.data | renamed
                # A title the user set is kept; only a generated one is rebuilt.
                title = (
                    plane_title(data)
                    if subentry.title == plane_title(subentry.data)
                    else subentry.title
                )
                updated |= hass.config_entries.async_update_subentry(
                    entry, subentry, data=data, title=title
                )
            # A retrying entry has no update listener; retry now, not after backoff.
            if updated and entry.state is ConfigEntryState.SETUP_RETRY:
                hass.config_entries.async_schedule_reload(entry.entry_id)

    hass.bus.async_listen(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        _async_sensor_renamed,
        event_filter=_async_is_rename,
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

    entry.async_on_unload(_async_reload_on_forecast_change(hass, entry))
    if CONF_LATITUDE not in entry.data:
        _async_refresh_on_home_move(hass, entry)

    return True


@callback
def _async_refresh_on_home_move(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> None:
    """Refresh when Home Assistant's location moves, for an entry following it."""
    coordinator = entry.runtime_data
    # Home may move on every GPS fix; this costs at most one extra request per
    # update interval, so the rate limit isn't spent on a camper on the road.
    debouncer = Debouncer(
        hass,
        LOGGER,
        cooldown=cast(timedelta, coordinator.update_interval).total_seconds(),
        immediate=True,
        function=coordinator.async_refresh,
    )

    @callback
    def _async_core_config_updated(_event: Event) -> None:
        forecast = coordinator.forecast
        # Other core config changes don't spend a request.
        if (hass.config.latitude, hass.config.longitude) != (
            forecast.latitude,
            forecast.longitude,
        ):
            debouncer.async_schedule_call()

    entry.async_on_unload(debouncer.async_shutdown)
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _async_core_config_updated)
    )


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
            # Not eager: the caller may still be updating the other planes, and a
            # reload that already unloaded the entry would make a flow reload again.
            hass.async_create_task(
                _async_reload(),
                f"forecast_solar reload {entry.entry_id}",
                eager_start=False,
            )

    return entry.add_update_listener(_async_entry_updated)


async def async_unload_entry(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
