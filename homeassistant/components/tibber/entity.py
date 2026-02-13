"""Shared entity base for Tibber sensors."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import TibberDataCoordinator, TibberHomeData, TibberRtDataCoordinator

if TYPE_CHECKING:
    from tibber import TibberHome


class TibberDataCoordinatorEntity(CoordinatorEntity[TibberDataCoordinator]):
    """Base entity for Tibber sensors using TibberDataCoordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TibberDataCoordinator,
        tibber_home: TibberHome,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._tibber_home = tibber_home
        self._home_name: str = tibber_home.name or tibber_home.home_id
        self._model: str | None = None
        self._device_name: str = self._home_name

    def _get_home_data(self) -> TibberHomeData | None:
        """Return cached home data from the coordinator."""
        data = cast(dict[str, TibberHomeData] | None, self.coordinator.data)
        if data is None:
            return None
        return data.get(self._tibber_home.home_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._tibber_home.home_id)},
            name=self._device_name,
            model=self._model,
        )


class TibberSensor:
    """Mixin for Tibber sensors that have a Tibber home and device info.

    Used as the first base for real-time sensors (TibberSensorRT with
    CoordinatorEntity["TibberRtDataCoordinator"]). Provides _tibber_home,
    _home_name, _model, _device_name and device_info; does not inherit
    CoordinatorEntity so the second base can be the coordinator entity.
    """

    def __init__(self, coordinator: object, tibber_home: TibberHome) -> None:
        """Initialize the mixin."""
        super().__init__(coordinator)  # type: ignore[call-arg]
        self._tibber_home = tibber_home
        self._home_name: str = tibber_home.name or tibber_home.home_id
        self._model: str | None = None
        self._device_name: str = self._home_name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._tibber_home.home_id)},
            name=self._device_name,
            model=self._model,
        )


class TibberSensorRT(TibberSensor, CoordinatorEntity[TibberRtDataCoordinator]):
    """Representation of a Tibber sensor for real time consumption."""

    def __init__(
        self,
        tibber_home: TibberHome,
        description: SensorEntityDescription,
        initial_state: float,
        coordinator: TibberRtDataCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, tibber_home=tibber_home)
        self.entity_description = description
        self._model = "Tibber Pulse"
        self._device_name = f"{self._model} {self._home_name}"

        self._attr_native_value = initial_state
        self._attr_last_reset: datetime | None = None
        self._attr_unique_id = f"{self._tibber_home.home_id}_rt_{description.key}"

        if description.key in ("accumulatedCost", "accumulatedReward"):
            self._attr_native_unit_of_measurement = tibber_home.currency

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._tibber_home.rt_subscription_running

    @callback
    def _handle_coordinator_update(self) -> None:
        if not (live_measurement := self.coordinator.get_live_measurement()):
            return
        state = live_measurement.get(self.entity_description.key)
        if state is None:
            return
        if self.entity_description.key in (
            "accumulatedConsumption",
            "accumulatedProduction",
        ):
            # Value is reset to 0 at midnight, but not always strictly increasing
            # due to hourly corrections.
            # If device is offline, last_reset should be updated when it comes
            # back online if the value has decreased
            ts_local = dt_util.parse_datetime(live_measurement["timestamp"])
            if ts_local is not None:
                if self._attr_last_reset is None or (
                    state < 0.5 * self._attr_native_value
                    and (
                        ts_local.hour == 0
                        or (ts_local - self._attr_last_reset) > timedelta(hours=24)
                    )
                ):
                    self._attr_last_reset = dt_util.as_utc(
                        ts_local.replace(hour=0, minute=0, second=0, microsecond=0)
                    )
        if self.entity_description.key == "powerFactor":
            state *= 100.0
        self._attr_native_value = state
        self.async_write_ha_state()
