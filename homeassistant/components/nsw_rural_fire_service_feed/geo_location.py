"""Support for NSW Rural Fire Service Feeds."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from aio_geojson_nsw_rfs_incidents.feed_entry import (
    NswRuralFireServiceIncidentsFeedEntry,
)
import voluptuous as vol

from homeassistant.components.geo_location import PLATFORM_SCHEMA, GeolocationEvent
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_LOCATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import NswRuralFireServiceFeedEntityManager
from .const import (
    CONF_CATEGORIES,
    DEFAULT_RADIUS_IN_KM,
    DOMAIN,
    FEED,
    SIGNAL_DELETE_ENTITY,
    SIGNAL_UPDATE_ENTITY,
    VALID_CATEGORIES,
)

_LOGGER = logging.getLogger(__name__)

ATTR_CATEGORY = "category"
ATTR_COUNCIL_AREA = "council_area"
ATTR_EXTERNAL_ID = "external_id"
ATTR_FIRE = "fire"
ATTR_PUBLICATION_DATE = "publication_date"
ATTR_RESPONSIBLE_AGENCY = "responsible_agency"
ATTR_SIZE = "size"
ATTR_STATUS = "status"
ATTR_TYPE = "type"

SOURCE = "nsw_rural_fire_service_feed"

# Deprecated.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_CATEGORIES, default=[]): vol.All(
            cv.ensure_list, [vol.In(VALID_CATEGORIES)]
        ),
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(float),
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the NSW Rural Fire Service Feeds platform."""
    manager: NswRuralFireServiceFeedEntityManager = hass.data[DOMAIN][FEED][
        entry.entry_id
    ]

    @callback
    def async_add_geolocation(
        feed_manager: NswRuralFireServiceFeedEntityManager,
        integration_id: str,
        external_id: str,
    ) -> None:
        """Add geolocation entity from feed."""
        new_entity = NswRuralFireServiceLocationEvent(
            feed_manager, integration_id, external_id
        )
        _LOGGER.debug("Adding geolocation %s", new_entity)
        async_add_entities([new_entity], True)

    manager.listeners.append(
        async_dispatcher_connect(
            hass, manager.async_event_new_entity(), async_add_geolocation
        )
    )
    # Do not wait for update here so that the setup can be completed and because an
    # update will fetch data from the feed via HTTP and then process that data.
    hass.async_create_task(manager.async_update())
    _LOGGER.debug("Geolocation setup done")


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the NSW Rural Fire Service Feed platform."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.6.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


class NswRuralFireServiceLocationEvent(GeolocationEvent):
    """Represents an external event with NSW Rural Fire Service data."""

    _attr_should_poll = False
    _attr_source = SOURCE
    _attr_unit_of_measurement = UnitOfLength.KILOMETERS

    def __init__(
        self,
        feed_manager: NswRuralFireServiceFeedEntityManager,
        integration_id: str,
        external_id: str,
    ) -> None:
        """Initialize entity with data from feed entry."""
        self._feed_manager = feed_manager
        self._external_id = external_id
        self._attr_unique_id = f"{integration_id}_{external_id}"
        self._category = None
        self._publication_date = None
        self._location = None
        self._council_area = None
        self._status = None
        self._type = None
        self._fire = None
        self._size = None
        self._responsible_agency = None
        self._remove_signal_delete: Callable[[], None]
        self._remove_signal_update: Callable[[], None]

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self._remove_signal_delete = async_dispatcher_connect(
            self.hass,
            SIGNAL_DELETE_ENTITY.format(self._external_id),
            self._delete_callback,
        )
        self._remove_signal_update = async_dispatcher_connect(
            self.hass,
            SIGNAL_UPDATE_ENTITY.format(self._external_id),
            self._update_callback,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        self._remove_signal_delete()
        self._remove_signal_update()

    @callback
    def _delete_callback(self) -> None:
        """Remove this entity."""
        self.hass.async_create_task(self.async_remove(force_remove=True))

    @callback
    def _update_callback(self) -> None:
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update this entity from the data held in the feed manager."""
        _LOGGER.debug("Updating %s", self._external_id)
        feed_entry = self._feed_manager.get_entry(self._external_id)
        if feed_entry:
            self._update_from_feed(feed_entry)

    def _update_from_feed(
        self, feed_entry: NswRuralFireServiceIncidentsFeedEntry
    ) -> None:
        """Update the internal state from the provided feed entry."""
        self._attr_name = feed_entry.title
        self._attr_distance = feed_entry.distance_to_home
        self._attr_latitude = feed_entry.coordinates[0]
        self._attr_longitude = feed_entry.coordinates[1]
        self._attr_attribution = feed_entry.attribution
        self._category = feed_entry.category
        self._publication_date = feed_entry.publication_date
        self._location = feed_entry.location
        self._council_area = feed_entry.council_area
        self._status = feed_entry.status
        self._type = feed_entry.type
        self._fire = feed_entry.fire
        self._size = feed_entry.size
        self._responsible_agency = feed_entry.responsible_agency

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self._fire:
            return "mdi:fire"
        return "mdi:alarm-light"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attributes = {}
        for key, value in (
            (ATTR_EXTERNAL_ID, self._external_id),
            (ATTR_CATEGORY, self._category),
            (ATTR_LOCATION, self._location),
            (ATTR_PUBLICATION_DATE, self._publication_date),
            (ATTR_COUNCIL_AREA, self._council_area),
            (ATTR_STATUS, self._status),
            (ATTR_TYPE, self._type),
            (ATTR_FIRE, self._fire),
            (ATTR_SIZE, self._size),
            (ATTR_RESPONSIBLE_AGENCY, self._responsible_agency),
        ):
            if value or isinstance(value, bool):
                attributes[key] = value
        return attributes
