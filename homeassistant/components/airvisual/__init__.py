"""The AirVisual component."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
from math import ceil
from typing import Any

from pyairvisual.cloud_api import (
    CloudAPI,
    InvalidKeyError,
    KeyExpiredError,
    UnauthorizedError,
)
from pyairvisual.errors import AirVisualError

from homeassistant.components import automation
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
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

# We use a raw string for the airvisual_pro domain (instead of importing the actual
# constant) so that we can avoid listing it as a dependency:
DOMAIN_AIRVISUAL_PRO = "airvisual_pro"

PLATFORMS = [Platform.SENSOR]

DEFAULT_ATTRIBUTION = "Data provided by AirVisual"

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AirVisual as config entry."""
    if CONF_API_KEY not in entry.data:
        # If this is a migrated AirVisual Pro entry, there's no actual setup to do;
        # that will be handled by the `airvisual_pro` domain:
        return False

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

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Reassess the interval between 2 server requests
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
                    context={"source": SOURCE_IMPORT},
                    data={
                        "import_source": source,
                        CONF_API_KEY: entry.data[CONF_API_KEY],
                        **geography,
                    },
                )
            )

    # 2 -> 3: Moving AirVisual Pro to its own domain
    elif version == 2:
        version = 3

        if entry.data[CONF_INTEGRATION_TYPE] == INTEGRATION_TYPE_NODE_PRO:
            device_registry = dr.async_get(hass)
            entity_registry = er.async_get(hass)
            ip_address = entry.data[CONF_IP_ADDRESS]

            # Store the existing Pro device before the migration removes it:
            old_device_entry = next(
                entry
                for entry in dr.async_entries_for_config_entry(
                    device_registry, entry.entry_id
                )
            )

            # Store the existing Pro entity entries (mapped by unique ID) before the
            # migration removes it:
            old_entity_entries: dict[str, er.RegistryEntry] = {
                entry.unique_id: entry
                for entry in er.async_entries_for_device(
                    entity_registry, old_device_entry.id, include_disabled_entities=True
                )
            }

            # Remove this config entry and create a new one under the `airvisual_pro`
            # domain:
            new_entry_data = {**entry.data}
            new_entry_data.pop(CONF_INTEGRATION_TYPE)
            tasks = [
                hass.config_entries.async_remove(entry.entry_id),
                hass.config_entries.flow.async_init(
                    DOMAIN_AIRVISUAL_PRO,
                    context={"source": SOURCE_IMPORT},
                    data=new_entry_data,
                ),
            ]
            await asyncio.gather(*tasks)

            # After the migration has occurred, grab the new config and device entries
            # (now under the `airvisual_pro` domain):
            new_config_entry = next(
                entry
                for entry in hass.config_entries.async_entries(DOMAIN_AIRVISUAL_PRO)
                if entry.data[CONF_IP_ADDRESS] == ip_address
            )
            new_device_entry = next(
                entry
                for entry in dr.async_entries_for_config_entry(
                    device_registry, new_config_entry.entry_id
                )
            )

            # Update the new device entry with any customizations from the old one:
            device_registry.async_update_device(
                new_device_entry.id,
                area_id=old_device_entry.area_id,
                disabled_by=old_device_entry.disabled_by,
                name_by_user=old_device_entry.name_by_user,
            )

            # Update the new entity entries with any customizations from the old ones:
            for new_entity_entry in er.async_entries_for_device(
                entity_registry, new_device_entry.id, include_disabled_entities=True
            ):
                if old_entity_entry := old_entity_entries.get(
                    new_entity_entry.unique_id
                ):
                    entity_registry.async_update_entity(
                        new_entity_entry.entity_id,
                        area_id=old_entity_entry.area_id,
                        device_class=old_entity_entry.device_class,
                        disabled_by=old_entity_entry.disabled_by,
                        hidden_by=old_entity_entry.hidden_by,
                        icon=old_entity_entry.icon,
                        name=old_entity_entry.name,
                        new_entity_id=old_entity_entry.entity_id,
                        unit_of_measurement=old_entity_entry.unit_of_measurement,
                    )

            # If any automations are using the old device ID, create a Repairs issues
            # with instructions on how to update it:
            if device_automations := automation.automations_with_device(
                hass, old_device_entry.id
            ):
                async_create_issue(
                    hass,
                    DOMAIN,
                    f"airvisual_pro_migration_{entry.entry_id}",
                    is_fixable=False,
                    is_persistent=True,
                    severity=IssueSeverity.WARNING,
                    translation_key="airvisual_pro_migration",
                    translation_placeholders={
                        "ip_address": ip_address,
                        "old_device_id": old_device_entry.id,
                        "new_device_id": new_device_entry.id,
                        "device_automations_string": ", ".join(
                            f"`{automation}`" for automation in device_automations
                        ),
                    },
                )
        else:
            entry.version = version

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

    # pylint: disable-next=hass-missing-super-call
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
