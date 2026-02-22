"""DataUpdateCoordinator for the BSB-Lan integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

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

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL_FAST, SCAN_INTERVAL_SLOW

if TYPE_CHECKING:
    from . import BSBLanConfigEntry

# Filter lists for optimized API calls - only fetch parameters we actually use
# This significantly reduces response time (~0.2s per parameter saved)
STATE_INCLUDE = ["current_temperature", "target_temperature", "hvac_mode"]
SENSOR_INCLUDE = ["current_temperature", "outside_temperature"]
DHW_STATE_INCLUDE = [
    "operating_mode",
    "nominal_setpoint",
    "dhw_actual_value_top_temperature",
]
DHW_CONFIG_INCLUDE = ["reduced_setpoint", "nominal_setpoint_max"]


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

    config_entry: BSBLanConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BSBLanConfigEntry,
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
        config_entry: BSBLanConfigEntry,
        client: BSBLAN,
    ) -> None:
        """Initialize the BSB-Lan fast coordinator."""
        super().__init__(
            hass,
            config_entry,
            client,
            name=f"{DOMAIN}_fast_{config_entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL_FAST,
        )

    async def _async_update_data(self) -> BSBLanFastData:
        """Fetch fast-changing data from the BSB-Lan device."""
        try:
            # Client is already initialized in async_setup_entry
            # Use include filtering to only fetch parameters we actually use
            # This reduces response time significantly (~0.2s per parameter)
            state = await self.client.state(include=STATE_INCLUDE)
            sensor = await self.client.sensor(include=SENSOR_INCLUDE)
            dhw = await self.client.hot_water_state(include=DHW_STATE_INCLUDE)

        except BSBLANAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed for BSB-Lan device"
            ) from err
        except BSBLANConnectionError as err:
            host = self.config_entry.data[CONF_HOST]
            raise UpdateFailed(
                f"Error while establishing connection with BSB-Lan device at {host}"
            ) from err

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
        config_entry: BSBLanConfigEntry,
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
            # Use include filtering to only fetch parameters we actually use
            dhw_config = await self.client.hot_water_config(include=DHW_CONFIG_INCLUDE)
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
