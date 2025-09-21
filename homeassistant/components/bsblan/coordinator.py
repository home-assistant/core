"""DataUpdateCoordinator for the BSB-Lan integration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
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
class BSBLanCoordinatorData:
    """BSBLan data stored in the Home Assistant data object."""

    # Fast-polling data (updated every 12 seconds)
    state: State
    sensor: Sensor
    dhw: HotWaterState  # Current DHW state (temperature, pump status)

    # Slow-polling data (updated every 5 minutes)
    dhw_config: HotWaterConfig | None = None  # DHW configuration settings
    dhw_schedule: HotWaterSchedule | None = None  # DHW schedule settings
    last_config_update: datetime | None = None  # Track when config was last updated


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
            update_interval=SCAN_INTERVAL_FAST,  # Use fast interval as base
        )
        self.client = client
        self._last_config_update = datetime.min

    def _get_update_interval(self) -> timedelta:
        """Get the update interval with a random offset.

        Use the fast scan interval and add a random number of seconds to avoid timeouts when
        the BSB-Lan device is already/still busy retrieving data,
        e.g. for MQTT or internal logging.
        """
        return SCAN_INTERVAL_FAST + timedelta(seconds=randint(1, 8))

    async def _async_update_data(self) -> BSBLanCoordinatorData:
        """Get data with selective updates based on polling intervals."""
        try:
            # initialize the client, this is cached and will only be called once
            await self.client.initialize()

            # Always fetch fast-changing data (every ~12 seconds)
            state = await self.client.state()
            sensor = await self.client.sensor()
            dhw = await self.client.hot_water_state()

            # Initialize variables for slow-changing data
            dhw_config: HotWaterConfig | None
            dhw_schedule: HotWaterSchedule | None
            last_config_update: datetime | None

            # Check if we need to update configuration data (every 5 minutes)
            now = datetime.now()
            needs_config_update = (now - self._last_config_update) >= SCAN_INTERVAL_SLOW

            if needs_config_update:
                # Fetch slow-changing configuration data
                try:
                    dhw_config = await self.client.hot_water_config()
                    dhw_schedule = await self.client.hot_water_schedule()
                    self._last_config_update = now
                    last_config_update = now

                    LOGGER.debug("Updated DHW config and schedule data")
                except (BSBLANConnectionError, BSBLANAuthError, AttributeError) as err:
                    # If config update fails, keep existing data and log error
                    LOGGER.warning("Failed to update DHW config data: %s", err)
                    dhw_config = self.data.dhw_config if self.data else None
                    dhw_schedule = self.data.dhw_schedule if self.data else None
                    last_config_update = (
                        self.data.last_config_update if self.data else None
                    )
            else:
                # Reuse previous config data
                dhw_config = self.data.dhw_config if self.data else None
                dhw_schedule = self.data.dhw_schedule if self.data else None
                last_config_update = self.data.last_config_update if self.data else None

        except BSBLANAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed for BSB-Lan device"
            ) from err
        except BSBLANConnectionError as err:
            host = self.config_entry.data[CONF_HOST] if self.config_entry else "unknown"
            raise UpdateFailed(
                f"Error while establishing connection with BSB-Lan device at {host}"
            ) from err

        # Update the interval with random jitter for next update
        self.update_interval = self._get_update_interval()

        return BSBLanCoordinatorData(
            state=state,
            sensor=sensor,
            dhw=dhw,
            dhw_config=dhw_config,
            dhw_schedule=dhw_schedule,
            last_config_update=last_config_update,
        )
