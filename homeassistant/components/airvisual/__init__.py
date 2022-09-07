"""The airvisual component."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from math import ceil
from typing import Any

from pyairvisual import CloudAPI, NodeSamba
from pyairvisual.errors import (
    AirVisualError,
    InvalidKeyError,
    KeyExpiredError,
    NodeProError,
    UnauthorizedError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    entity_registry,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_CITY,
    CONF_COUNTRY,
    CONF_GEOGRAPHIES,
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    INTEGRATION_TYPE_GEOGRAPHY_NAME,
    INTEGRATION_TYPE_NODE_PRO,
    LOGGER,
)

PLATFORMS = [Platform.SENSOR]

DEFAULT_ATTRIBUTION = "Data provided by AirVisual"
DEFAULT_NODE_PRO_UPDATE_INTERVAL = timedelta(minutes=1)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


@callback
def async_get_geography_id(geography_dict: Mapping[str, Any]) -> str:
    """Generate a unique ID from a geography dict."""
    if CONF_CITY in geography_dict:
        return ", ".join(
            (
                geography_dict[CONF_CITY],
                geography_dict[CONF_STATE],
                geography_dict[CONF_COUNTRY],
            )
        )
    return ", ".join(
        (str(geography_dict[CONF_LATITUDE]), str(geography_dict[CONF_LONGITUDE]))
    )


@callback
def async_get_cloud_api_update_interval(
    hass: HomeAssistant, api_key: str, num_consumers: int
) -> timedelta:
    """Get a leveled scan interval for a particular cloud API key.

    This will shift based on the number of active consumers, thus keeping the user
    under the monthly API limit.
    """
    # Assuming 10,000 calls per month and a "largest possible month" of 31 days; note
    # that we give a buffer of 1500 API calls for any drift, restarts, etc.:
    minutes_between_api_calls = ceil(num_consumers * 31 * 24 * 60 / 8500)

    LOGGER.debug(
        "Leveling API key usage (%s): %s consumers, %s minutes between updates",
        api_key,
        num_consumers,
        minutes_between_api_calls,
    )

    return timedelta(minutes=minutes_between_api_calls)


@callback
def async_get_cloud_coordinators_by_api_key(
    hass: HomeAssistant, api_key: str
) -> list[DataUpdateCoordinator]:
    """Get all DataUpdateCoordinator objects related to a particular API key."""
    return [
        coordinator
        for entry_id, coordinator in hass.data[DOMAIN].items()
        if (entry := hass.config_entries.async_get_entry(entry_id))
        and entry.data.get(CONF_API_KEY) == api_key
    ]


@callback
def async_sync_geo_coordinator_update_intervals(
    hass: HomeAssistant, api_key: str
) -> None:
    """Sync the update interval for geography-based data coordinators (by API key)."""
    coordinators = async_get_cloud_coordinators_by_api_key(hass, api_key)

    if not coordinators:
        return

    update_interval = async_get_cloud_api_update_interval(
        hass, api_key, len(coordinators)
    )

    for coordinator in coordinators:
        LOGGER.debug(
            "Updating interval for coordinator: %s, %s",
            coordinator.name,
            update_interval,
        )
        coordinator.update_interval = update_interval


@callback
def _standardize_geography_config_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Ensure that geography config entries have appropriate properties."""
    entry_updates = {}

    if not entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = entry.data[CONF_API_KEY]
    if not entry.options:
        # If the config entry doesn't already have any options set, set defaults:
        entry_updates["options"] = {CONF_SHOW_ON_MAP: True}
    if entry.data.get(CONF_INTEGRATION_TYPE) not in [
        INTEGRATION_TYPE_GEOGRAPHY_COORDS,
        INTEGRATION_TYPE_GEOGRAPHY_NAME,
    ]:
        # If the config entry data doesn't contain an integration type that we know
        # about, infer it from the data we have:
        entry_updates["data"] = {**entry.data}
        if CONF_CITY in entry.data:
            entry_updates["data"][
                CONF_INTEGRATION_TYPE
            ] = INTEGRATION_TYPE_GEOGRAPHY_NAME
        else:
            entry_updates["data"][
                CONF_INTEGRATION_TYPE
            ] = INTEGRATION_TYPE_GEOGRAPHY_COORDS

    if not entry_updates:
        return

    hass.config_entries.async_update_entry(entry, **entry_updates)


@callback
def _standardize_node_pro_config_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ensure that Node/Pro config entries have appropriate properties."""
    entry_updates: dict[str, Any] = {}

    if CONF_INTEGRATION_TYPE not in entry.data:
        # If the config entry data doesn't contain the integration type, add it:
        entry_updates["data"] = {
            **entry.data,
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_NODE_PRO,
        }

    if not entry_updates:
        return

    hass.config_entries.async_update_entry(entry, **entry_updates)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AirVisual as config entry."""
    if CONF_API_KEY in entry.data:
        _standardize_geography_config_entry(hass, entry)

        websession = aiohttp_client.async_get_clientsession(hass)
        cloud_api = CloudAPI(entry.data[CONF_API_KEY], session=websession)

        async def async_update_data() -> dict[str, Any]:
            """Get new data from the API."""
            if CONF_CITY in entry.data:
                api_coro = cloud_api.air_quality.city(
                    entry.data[CONF_CITY],
                    entry.data[CONF_STATE],
                    entry.data[CONF_COUNTRY],
                )
            else:
                api_coro = cloud_api.air_quality.nearest_city(
                    entry.data[CONF_LATITUDE],
                    entry.data[CONF_LONGITUDE],
                )

            try:
                return await api_coro
            except (InvalidKeyError, KeyExpiredError, UnauthorizedError) as ex:
                raise ConfigEntryAuthFailed from ex
            except AirVisualError as err:
                raise UpdateFailed(f"Error while retrieving data: {err}") from err

        coordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=async_get_geography_id(entry.data),
            # We give a placeholder update interval in order to create the coordinator;
            # then, below, we use the coordinator's presence (along with any other
            # coordinators using the same API key) to calculate an actual, leveled
            # update interval:
            update_interval=timedelta(minutes=5),
            update_method=async_update_data,
        )

        # Only geography-based entries have options:
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    else:
        # Remove outdated air_quality entities from the entity registry if they exist:
        ent_reg = entity_registry.async_get(hass)
        for entity_entry in [
            e
            for e in ent_reg.entities.values()
            if e.config_entry_id == entry.entry_id
            and e.entity_id.startswith("air_quality")
        ]:
            LOGGER.debug(
                'Removing deprecated air_quality entity: "%s"', entity_entry.entity_id
            )
            ent_reg.async_remove(entity_entry.entity_id)

        _standardize_node_pro_config_entry(hass, entry)

        async def async_update_data() -> dict[str, Any]:
            """Get new data from the API."""
            try:
                async with NodeSamba(
                    entry.data[CONF_IP_ADDRESS], entry.data[CONF_PASSWORD]
                ) as node:
                    return await node.async_get_latest_measurements()
            except NodeProError as err:
                raise UpdateFailed(f"Error while retrieving data: {err}") from err

        coordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name="Node/Pro data",
            update_interval=DEFAULT_NODE_PRO_UPDATE_INTERVAL,
            update_method=async_update_data,
        )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Reassess the interval between 2 server requests
    if CONF_API_KEY in entry.data:
        async_sync_geo_coordinator_update_intervals(hass, entry.data[CONF_API_KEY])

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    version = entry.version

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: One geography per config entry
    if version == 1:
        version = entry.version = 2

        # Update the config entry to only include the first geography (there is always
        # guaranteed to be at least one):
        geographies = list(entry.data[CONF_GEOGRAPHIES])
        first_geography = geographies.pop(0)
        first_id = async_get_geography_id(first_geography)

        hass.config_entries.async_update_entry(
            entry,
            unique_id=first_id,
            title=f"Cloud API ({first_id})",
            data={CONF_API_KEY: entry.data[CONF_API_KEY], **first_geography},
        )

        # For any geographies that remain, create a new config entry for each one:
        for geography in geographies:
            if CONF_LATITUDE in geography:
                source = "geography_by_coords"
            else:
                source = "geography_by_name"
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": source},
                    data={CONF_API_KEY: entry.data[CONF_API_KEY], **geography},
                )
            )

    LOGGER.info("Migration to version %s successful", version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an AirVisual config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if CONF_API_KEY in entry.data:
            # Re-calculate the update interval period for any remaining consumers of
            # this API key:
            async_sync_geo_coordinator_update_intervals(hass, entry.data[CONF_API_KEY])

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class AirVisualEntity(CoordinatorEntity):
    """Define a generic AirVisual entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._entry = entry
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def update() -> None:
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(self.coordinator.async_add_listener(update))

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError
