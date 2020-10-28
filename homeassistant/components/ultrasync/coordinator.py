"""Provides the UltraSync DataUpdateCoordinator."""
from datetime import timedelta
import logging

from ultrasync import UltraSync

from async_timeout import timeout

from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    CONF_PIN,
    CONF_USERNAME,
    CONF_HOST,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class UltraSyncDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching UltraSync data."""

    def __init__(self, hass: HomeAssistantType, *, config: dict, options: dict):
        """Initialize global UltraSync data updater."""
        self.hub = UltraSync(
            user=config[CONF_USERNAME],
            pin=config[CONF_PIN],
            host=config[CONF_HOST],
        )

        self._init = False

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
            response = {
                'Area1State': 'unknown',
                'Area2State': 'unknown',
                'Area3State': 'unknown',
                'Area4State': 'unknown',
            }

            # Update our details
            details = self.hub.details()
            if details:
                for bank, zone in self.hub.zones.items():
                    if self._zone_delta.get(zone['bank']) != zone['sequence']:
                        self.hass.bus.fire(
                            "ultrasync_sensor_update",
                            {
                                "sensor": zone['bank'] + 1,
                                "name": zone['name'],
                                "status": zone['status'],
                            },
                        )

                        # Update our sequence
                        self._zone_delta[zone['bank']] = zone['sequence']

                for area in details.get('areas', []):
                    if self._area_delta.get(area['bank']) != area['sequence']:
                        self.hass.bus.fire(
                            "ultrasync_area_update",
                            {
                                "area": area['bank'] + 1,
                                "name": area['name'],
                                "status": area['status'],
                            },
                        )

                        # Update our sequence
                        self._area_delta[area['bank']] = area['sequence']

                    # Set our state:
                    response['Area{}State'.format(area['bank'] + 1)] = area['status']

            self._init = True

            # Return our response
            return response

        # The hub can sometimes take a very long time to respond; wait
        # 10 seconds before giving up
        async with timeout(10):
            return await self.hass.async_add_executor_job(_update_data)
