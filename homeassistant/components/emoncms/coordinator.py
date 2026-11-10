"""DataUpdateCoordinator for the emoncms integration."""

from datetime import timedelta
from typing import Any, override

from pyemoncms import EmoncmsClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_MESSAGE, CONF_SUCCESS, FEED_ID, FEED_TAG, LOGGER

type EmonCMSConfigEntry = ConfigEntry[EmoncmsCoordinator]


class EmoncmsCoordinator(DataUpdateCoordinator[list[dict[str, Any]] | None]):
    """Emoncms Data Update Coordinator."""

    config_entry: EmonCMSConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EmonCMSConfigEntry,
        emoncms_client: EmoncmsClient,
    ) -> None:
        """Initialize the emoncms data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="emoncms_coordinator",
            update_interval=timedelta(seconds=60),
        )
        self.emoncms_client = emoncms_client

    @override
    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from API endpoint."""
        data = await self.emoncms_client.async_request("/feed/list.json")
        if not data[CONF_SUCCESS]:
            raise UpdateFailed
        feeds = data[CONF_MESSAGE]
        if self.data:
            old_tags = {feed[FEED_ID]: feed[FEED_TAG] for feed in self.data}
            if any(
                old_tags.get(feed[FEED_ID], feed[FEED_TAG]) != feed[FEED_TAG]
                for feed in feeds
            ):
                # Devices are derived from tags at setup; one reload per poll
                self.hass.config_entries.async_schedule_reload(
                    self.config_entry.entry_id
                )
        return feeds
