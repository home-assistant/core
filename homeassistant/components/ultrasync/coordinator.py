"""Provides the UltraSync DataUpdateCoordinator."""
from datetime import timedelta
import logging

from async_timeout import timeout
import ultrasync

from homeassistant.const import CONF_HOST, CONF_PIN, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SENSOR_UPDATE_LISTENER

_LOGGER = logging.getLogger(__name__)


class UltraSyncDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching UltraSync data."""

    def __init__(self, hass: HomeAssistantType, *, config: dict, options: dict):
        """Initialize global UltraSync data updater."""
        self.hub = ultrasync.UltraSync(
            user=config[CONF_USERNAME],
            pin=config[CONF_PIN],
            host=config[CONF_HOST],
        )

        # Used to track delta (for change tracking)
        self._area_delta = {}
        self._zone_delta = {}

        update_interval = timedelta(seconds=options[CONF_SCAN_INTERVAL])

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from UltraSync Hub."""

        def _update_data() -> dict:
            """Fetch data from UltraSync via sync functions."""

            # initialize our response
            response = {}

            # Update our details
            details = self.hub.details(max_age_sec=0)
            if details:
                async_dispatcher_send(
                    self.hass,
                    SENSOR_UPDATE_LISTENER,
                    details["areas"],
                    details["zones"],
                )

                for zone in details["zones"]:
                    if self._zone_delta.get(zone["bank"]) != zone["sequence"]:
                        self.hass.bus.fire(
                            "ultrasync_zone_update",
                            {
                                "sensor": zone["bank"] + 1,
                                "name": zone["name"],
                                "status": zone["status"],
                            },
                        )

                        # Update our sequence
                        self._zone_delta[zone["bank"]] = zone["sequence"]

                    # Set our state:
                    response["zone{:0>2}_state".format(zone["bank"] + 1)] = zone[
                        "status"
                    ]

                for area in details["areas"]:
                    if self._area_delta.get(area["bank"]) != area["sequence"]:
                        self.hass.bus.fire(
                            "ultrasync_area_update",
                            {
                                "area": area["bank"] + 1,
                                "name": area["name"],
                                "status": area["status"],
                            },
                        )

                        # Update our sequence
                        self._area_delta[area["bank"]] = area["sequence"]

                    # Set our state:
                    response["area{:0>2}_state".format(area["bank"] + 1)] = area[
                        "status"
                    ]

            # Return our response
            return response

        # The hub can sometimes take a very long time to respond; wait
        # 10 seconds before giving up
        async with timeout(10):
            return await self.hass.async_add_executor_job(_update_data)
