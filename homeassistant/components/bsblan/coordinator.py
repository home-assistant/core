"""DataUpdateCoordinator for the BSB-LAN integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, override

from bsblan import (
    BSBLAN,
    BSBLANAuthError,
    BSBLANConnectionError,
    BSBLANError,
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
STATE_INCLUDE = [
    "current_temperature",
    "target_temperature",
    "hvac_mode",
    "hvac_action",
]
SENSOR_INCLUDE = ["current_temperature", "outside_temperature", "total_energy"]
DHW_STATE_INCLUDE = [
    "operating_mode",
    "nominal_setpoint",
    "dhw_actual_value_top_temperature",
]
DHW_CONFIG_INCLUDE = ["reduced_setpoint", "nominal_setpoint_max"]


@dataclass
class BSBLanFastData:
    """BSBLan fast-polling data."""

    states: dict[int, State]
    sensor: Sensor
    dhw: HotWaterState | None = None


@dataclass
class BSBLanSlowData:
    """BSBLan slow-polling data."""

    dhw_config: HotWaterConfig | None = None
    dhw_schedule: HotWaterSchedule | None = None


class BSBLanCoordinator[T](DataUpdateCoordinator[T]):
    """Base BSB-LAN coordinator."""

    config_entry: BSBLanConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BSBLanConfigEntry,
        client: BSBLAN,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the BSB-LAN coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.client = client


class BSBLanFastCoordinator(BSBLanCoordinator[BSBLanFastData]):
    """The BSB-LAN fast update coordinator for frequently changing data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BSBLanConfigEntry,
        client: BSBLAN,
        circuits: list[int],
    ) -> None:
        """Initialize the BSB-LAN fast coordinator."""
        super().__init__(
            hass,
            config_entry,
            client,
            name=f"{DOMAIN}_fast_{config_entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL_FAST,
        )
        self.circuits: list[int] = circuits

    @override
    async def _async_update_data(self) -> BSBLanFastData:
        """Fetch fast-changing data from the BSB-LAN device."""
        states: dict[int, State] = {}
        host = self.config_entry.data[CONF_HOST]
        try:
            # Use include filtering to only fetch parameters we actually use.
            # BSB-LAN is a serial bus — it processes one parameter at a time,
            # so concurrent requests offer no speed benefit over sequential.
            for circuit in self.circuits:
                try:
                    states[circuit] = await self.client.state(
                        include=STATE_INCLUDE, circuit=circuit
                    )
                except BSBLANAuthError, BSBLANConnectionError:
                    raise
                except BSBLANError as err:
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="coordinator_state_error",
                        translation_placeholders={
                            "host": host,
                            "circuit": str(circuit),
                        },
                    ) from err
            sensor = await self.client.sensor(include=SENSOR_INCLUDE)

        except BSBLANAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="coordinator_auth_error",
            ) from err
        except BSBLANConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="coordinator_connection_error",
                translation_placeholders={"host": host},
            ) from err

        # Fetch DHW state separately - device may not support hot water
        dhw: HotWaterState | None = None
        try:
            dhw = await self.client.hot_water_state(include=DHW_STATE_INCLUDE)
        except BSBLANError:
            # Preserve last known DHW state if available (entity may depend on it)
            if self.data:
                dhw = self.data.dhw
            LOGGER.debug(
                "DHW (Domestic Hot Water) state not available on device at %s",
                self.config_entry.data[CONF_HOST],
            )

        return BSBLanFastData(
            states=states,
            sensor=sensor,
            dhw=dhw,
        )


class BSBLanSlowCoordinator(BSBLanCoordinator[BSBLanSlowData]):
    """The BSB-LAN slow update coordinator for infrequently changing data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BSBLanConfigEntry,
        client: BSBLAN,
    ) -> None:
        """Initialize the BSB-LAN slow coordinator."""
        super().__init__(
            hass,
            config_entry,
            client,
            name=f"{DOMAIN}_slow_{config_entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL_SLOW,
        )
        # Serialize interval polls and off-interval refreshes so a
        # schedule-write refresh completing during a poll's device await
        # cannot be overwritten with the poll's stale pre-await snapshot.
        self._refresh_lock = asyncio.Lock()
        self._dhw_schedule_supported = True

    @override
    async def _async_update_data(self) -> BSBLanSlowData:
        """Fetch slow-changing data from the BSB-LAN device.

        Only the DHW config is polled here. The schedule changes rarely and is
        refreshed separately (on startup and after a write) to avoid extra
        serial-bus traffic on every interval, so it is carried over from the
        previous update.
        """
        async with self._refresh_lock:
            try:
                # Client is already initialized in async_setup_entry
                # Use include filtering to only fetch parameters we actually use
                dhw_config = await self.client.hot_water_config(
                    include=DHW_CONFIG_INCLUDE
                )
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
            except BSBLANError, AttributeError:
                # Device does not support DHW functionality
                LOGGER.debug(
                    "DHW (Domestic Hot Water) not available on device at %s",
                    self.config_entry.data[CONF_HOST],
                )
                dhw_config = None

            previous = self.data
            dhw_schedule = previous.dhw_schedule if previous else None

            # The schedule is otherwise fetched only off the interval. If the
            # startup fetch failed (e.g. a transient connection error) no
            # schedule is cached yet, so retry here until the first success.
            # Once cached, subsequent polls carry it forward without re-fetching.
            if dhw_schedule is None and self._dhw_schedule_supported:
                dhw_schedule = await self._async_fetch_dhw_schedule()

            return BSBLanSlowData(
                dhw_config=dhw_config,
                dhw_schedule=dhw_schedule,
            )

    async def async_refresh_slow_data(self) -> None:
        """Fetch DHW config and schedule off the polling interval.

        Runs on startup (in the background) and after a schedule is written, so
        these rarely changing values neither block startup nor add serial-bus
        traffic on every interval. Values that fail to fetch keep their
        previous value.
        """
        async with self._refresh_lock:
            dhw_config = await self._async_fetch_dhw_config()
            dhw_schedule = await self._async_fetch_dhw_schedule()

            previous = self.data or BSBLanSlowData()
            self.async_set_updated_data(
                BSBLanSlowData(
                    dhw_config=dhw_config or previous.dhw_config,
                    dhw_schedule=dhw_schedule or previous.dhw_schedule,
                )
            )

    async def _async_fetch_dhw_config(self) -> HotWaterConfig | None:
        """Fetch the DHW config, returning None if unavailable."""
        try:
            return await self.client.hot_water_config(include=DHW_CONFIG_INCLUDE)
        except BSBLANError, AttributeError, TimeoutError:
            LOGGER.debug(
                "DHW config not available on device at %s",
                self.config_entry.data[CONF_HOST],
            )
            return None

    async def _async_fetch_dhw_schedule(self) -> HotWaterSchedule | None:
        """Fetch the DHW schedule, returning None if unavailable."""
        if not self._dhw_schedule_supported:
            return None
        try:
            return await self.client.hot_water_schedule()
        except BSBLANConnectionError, BSBLANAuthError, TimeoutError:
            LOGGER.debug(
                "DHW schedule not available on device at %s",
                self.config_entry.data[CONF_HOST],
            )
            return None
        except BSBLANError, AttributeError:
            self._dhw_schedule_supported = False
            LOGGER.debug(
                "DHW schedule is not supported by device at %s",
                self.config_entry.data[CONF_HOST],
            )
            return None
