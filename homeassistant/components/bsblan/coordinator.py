"""DataUpdateCoordinator for the BSB-Lan integration."""

from dataclasses import dataclass
from datetime import timedelta
from random import randint

from bsblan import (
    BSBLAN,
    BSBLANAuthError,
    BSBLANConnectionError,
    HotWaterConfig,
    HotWaterSchedule,
    HotWaterState,
    Sensor,
    State,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL_FAST, SCAN_INTERVAL_SLOW


@dataclass
class BSBLanFastData:
    """BSBLan fast-polling data."""

    state: State
    sensor: Sensor
    dhw: HotWaterState


@dataclass
class BSBLanSlowData:
    """BSBLan slow-polling data."""

    dhw_config: HotWaterConfig | None = None
    dhw_schedule: HotWaterSchedule | None = None


class BSBLanCoordinator[T](DataUpdateCoordinator[T]):
    """Base BSB-Lan coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: BSBLAN,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the BSB-Lan coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.client = client


class BSBLanFastCoordinator(BSBLanCoordinator[BSBLanFastData]):
    """The BSB-Lan fast update coordinator for frequently changing data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: BSBLAN,
    ) -> None:
        """Initialize the BSB-Lan fast coordinator."""
        super().__init__(
            hass,
            config_entry,
            client,
            name=f"{DOMAIN}_fast_{config_entry.data[CONF_HOST]}",
            update_interval=self._get_update_interval(),
        )

    def _get_update_interval(self) -> timedelta:
        """Get the update interval with a random offset.

        Add a random number of seconds to avoid timeouts when
        the BSB-Lan device is already/still busy retrieving data,
        e.g. for MQTT or internal logging.
        """
        return SCAN_INTERVAL_FAST + timedelta(seconds=randint(1, 8))

    async def _async_update_data(self) -> BSBLanFastData:
        """Fetch fast-changing data from the BSB-Lan device."""
        try:
            # Client is already initialized in async_setup_entry
            # Fetch fast-changing data (state, sensor, DHW state)
            state = await self.client.state()
            sensor = await self.client.sensor()
            dhw = await self.client.hot_water_state()

        except BSBLANAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed for BSB-Lan device"
            ) from err
        except BSBLANConnectionError as err:
            host = self.config_entry.data[CONF_HOST]
            raise UpdateFailed(
                f"Error while establishing connection with BSB-Lan device at {host}"
            ) from err

        # Update the interval with random jitter for next update
        self.update_interval = self._get_update_interval()

        return BSBLanFastData(
            state=state,
            sensor=sensor,
            dhw=dhw,
        )


class BSBLanSlowCoordinator(BSBLanCoordinator[BSBLanSlowData]):
    """The BSB-Lan slow update coordinator for infrequently changing data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: BSBLAN,
    ) -> None:
        """Initialize the BSB-Lan slow coordinator."""
        super().__init__(
            hass,
            config_entry,
            client,
            name=f"{DOMAIN}_slow_{config_entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL_SLOW,
        )

    async def _async_update_data(self) -> BSBLanSlowData:
        """Fetch slow-changing data from the BSB-Lan device."""
        try:
            # Client is already initialized in async_setup_entry
            # Fetch slow-changing configuration data
            dhw_config = await self.client.hot_water_config()
            dhw_schedule = await self.client.hot_water_schedule()

        except AttributeError:
            # Device does not support DHW functionality
            LOGGER.debug(
                "DHW (Domestic Hot Water) not available on device at %s",
                self.config_entry.data[CONF_HOST],
            )
            return BSBLanSlowData()
        except (BSBLANConnectionError, BSBLANAuthError) as err:
            # If config update fails, keep existing data
            LOGGER.debug(
                "Failed to fetch DHW config from %s: %s",
                self.config_entry.data[CONF_HOST],
                err,
            )
            if self.data:
                return self.data
            # First fetch failed, return empty data
            return BSBLanSlowData()

        return BSBLanSlowData(
            dhw_config=dhw_config,
            dhw_schedule=dhw_schedule,
        )
