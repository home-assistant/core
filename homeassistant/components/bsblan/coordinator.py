"""DataUpdateCoordinator for the BSB-Lan integration."""

from dataclasses import dataclass
from datetime import timedelta
from random import randint

from bsblan import BSBLAN, BSBLANConnectionError, HotWaterState, Sensor, State

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


@dataclass
class BSBLanCoordinatorData:
    """BSBLan data stored in the Home Assistant data object."""

    state: State
    sensor: Sensor
    dhw: HotWaterState


class BSBLanUpdateCoordinator(DataUpdateCoordinator[BSBLanCoordinatorData]):
    """The BSB-Lan update coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: BSBLAN,
    ) -> None:
        """Initialize the BSB-Lan coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.data[CONF_HOST]}",
            update_interval=self._get_update_interval(),
        )
        self.client = client

    def _get_update_interval(self) -> timedelta:
        """Get the update interval with a random offset.

        Use the default scan interval and add a random number of seconds to avoid timeouts when
        the BSB-Lan device is already/still busy retrieving data,
        e.g. for MQTT or internal logging.
        """
        return SCAN_INTERVAL + timedelta(seconds=randint(1, 8))

    async def _async_update_data(self) -> BSBLanCoordinatorData:
        """Get state and sensor data from BSB-Lan device."""
        try:
            # initialize the client, this is cached and will only be called once
            await self.client.initialize()

            state = await self.client.state()
            sensor = await self.client.sensor()
            dhw = await self.client.hot_water_state()
        except BSBLANConnectionError as err:
            host = self.config_entry.data[CONF_HOST] if self.config_entry else "unknown"
            raise UpdateFailed(
                f"Error while establishing connection with BSB-Lan device at {host}"
            ) from err

        self.update_interval = self._get_update_interval()
        return BSBLanCoordinatorData(state=state, sensor=sensor, dhw=dhw)
