"""Entity representing a Jewish Calendar sensor."""

from abc import abstractmethod
import datetime as dt
import logging

from hdate import HDateInfo, Zmanim
from hdate.translator import set_language

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers import event
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import JewishCalendarConfigEntry, JewishCalendarDataResults

_LOGGER = logging.getLogger(__name__)


class JewishCalendarEntity(Entity):
    """An HA implementation for Jewish Calendar entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _update_unsub: CALLBACK_TYPE | None = None

    def __init__(
        self,
        config_entry: JewishCalendarConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize a Jewish Calendar entity."""
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
        )
        self.coordinator = config_entry.runtime_data
        set_language(self.coordinator.config_data.language)

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        self._schedule_update()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._update_unsub:
            self._update_unsub()
            self._update_unsub = None
        return await super().async_will_remove_from_hass()

    @abstractmethod
    def _update_times(self, zmanim: Zmanim) -> list[dt.datetime | None]:
        """Return a list of times to update the sensor."""

    def _schedule_update(self) -> None:
        """Schedule the next update of the sensor."""
        now = dt_util.now()
        zmanim = self.coordinator.data.results.zmanim
        update = dt_util.start_of_local_day() + dt.timedelta(days=1)

        for update_time in self._update_times(zmanim):
            if update_time is not None and now < update_time < update:
                update = update_time

        if self._update_unsub:
            self._update_unsub()
        self._update_unsub = event.async_track_point_in_time(
            self.hass, self._update, update
        )

    @callback
    def _update(self, now: dt.datetime | None = None) -> None:
        """Update the sensor data."""
        self._update_unsub = None
        self._schedule_update()
        self.create_results(now)
        self.async_write_ha_state()

    def create_results(self, now: dt.datetime | None = None) -> None:
        """Create the results for the sensor."""
        if now is None:
            now = dt_util.now()

        _LOGGER.debug("Now: %s Location: %r", now, self.coordinator.data.location)

        today = now.date()
        zmanim = self.coordinator.data.results.zmanim
        dateinfo = HDateInfo(today, diaspora=self.coordinator.data.diaspora)
        self.coordinator.data.results = JewishCalendarDataResults(dateinfo, zmanim)
