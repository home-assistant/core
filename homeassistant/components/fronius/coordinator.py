"""DataUpdateCoordinators for the Fronius integration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import TYPE_CHECKING, Any, TypeVar

from pyfronius import BadStatusError, FroniusError

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    SOLAR_NET_ID_POWER_FLOW,
    SOLAR_NET_ID_SYSTEM,
    FroniusDeviceInfo,
    SolarNetId,
)
from .sensor import (
    INVERTER_ENTITY_DESCRIPTIONS,
    LOGGER_ENTITY_DESCRIPTIONS,
    METER_ENTITY_DESCRIPTIONS,
    OHMPILOT_ENTITY_DESCRIPTIONS,
    POWER_FLOW_ENTITY_DESCRIPTIONS,
    STORAGE_ENTITY_DESCRIPTIONS,
)

if TYPE_CHECKING:
    from . import FroniusSolarNet
    from .sensor import _FroniusSensorEntity

    _FroniusEntityT = TypeVar("_FroniusEntityT", bound=_FroniusSensorEntity)


class FroniusCoordinatorBase(
    ABC, DataUpdateCoordinator[dict[SolarNetId, dict[str, Any]]]
):
    """Query Fronius endpoint and keep track of seen conditions."""

    default_interval: timedelta
    error_interval: timedelta
    valid_descriptions: list[SensorEntityDescription]

    MAX_FAILED_UPDATES = 3

    def __init__(self, *args: Any, solar_net: FroniusSolarNet, **kwargs: Any) -> None:
        """Set up the FroniusCoordinatorBase class."""
        self._failed_update_count = 0
        self.solar_net = solar_net
        # unregistered_keys are used to create entities in platform module
        self.unregistered_keys: dict[SolarNetId, set[str]] = {}
        super().__init__(*args, update_interval=self.default_interval, **kwargs)

    @abstractmethod
    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""

    async def _async_update_data(self) -> dict[SolarNetId, Any]:
        """Fetch the latest data from the source."""
        async with self.solar_net.coordinator_lock:
            try:
                data = await self._update_method()
            except FroniusError as err:
                self._failed_update_count += 1
                if self._failed_update_count == self.MAX_FAILED_UPDATES:
                    self.update_interval = self.error_interval
                raise UpdateFailed(err) from err

            if self._failed_update_count != 0:
                self._failed_update_count = 0
                self.update_interval = self.default_interval

            for solar_net_id in data:
                if solar_net_id not in self.unregistered_keys:
                    # id seen for the first time
                    self.unregistered_keys[solar_net_id] = {
                        desc.key for desc in self.valid_descriptions
                    }
            return data

    @callback
    def add_entities_for_seen_keys(
        self,
        async_add_entities: AddEntitiesCallback,
        entity_constructor: type[_FroniusEntityT],
    ) -> None:
        """
        Add entities for received keys and registers listener for future seen keys.

        Called from a platforms `async_setup_entry`.
        """

        @callback
        def _add_entities_for_unregistered_keys() -> None:
            """Add entities for keys seen for the first time."""
            new_entities: list = []
            for solar_net_id, device_data in self.data.items():
                for key in self.unregistered_keys[solar_net_id].intersection(
                    device_data
                ):
                    if device_data[key]["value"] is None:
                        continue
                    new_entities.append(entity_constructor(self, key, solar_net_id))
                    self.unregistered_keys[solar_net_id].remove(key)
            if new_entities:
                async_add_entities(new_entities)

        _add_entities_for_unregistered_keys()
        self.solar_net.cleanup_callbacks.append(
            self.async_add_listener(_add_entities_for_unregistered_keys)
        )


class FroniusInverterUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius device inverter endpoint and keep track of seen conditions."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)
    valid_descriptions = INVERTER_ENTITY_DESCRIPTIONS

    SILENT_RETRIES = 3

    def __init__(
        self, *args: Any, inverter_info: FroniusDeviceInfo, **kwargs: Any
    ) -> None:
        """Set up a Fronius inverter device scope coordinator."""
        super().__init__(*args, **kwargs)
        self.inverter_info = inverter_info

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        # almost 1% of `current_inverter_data` requests on Symo devices result in
        # `BadStatusError Code: 8 - LNRequestTimeout` due to flaky internal
        # communication between the logger and the inverter.
        for silent_retry in range(self.SILENT_RETRIES):
            try:
                data = await self.solar_net.fronius.current_inverter_data(
                    self.inverter_info.solar_net_id
                )
            except BadStatusError as err:
                if silent_retry == (self.SILENT_RETRIES - 1):
                    raise err
                continue
            break
        # wrap a single devices data in a dict with solar_net_id key for
        # FroniusCoordinatorBase _async_update_data and add_entities_for_seen_keys
        return {self.inverter_info.solar_net_id: data}


class FroniusLoggerUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius logger info endpoint and keep track of seen conditions."""

    default_interval = timedelta(hours=1)
    error_interval = timedelta(hours=1)
    valid_descriptions = LOGGER_ENTITY_DESCRIPTIONS

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.solar_net.fronius.current_logger_info()
        return {SOLAR_NET_ID_SYSTEM: data}


class FroniusMeterUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius system meter endpoint and keep track of seen conditions."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)
    valid_descriptions = METER_ENTITY_DESCRIPTIONS

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.solar_net.fronius.current_system_meter_data()
        return data["meters"]  # type: ignore[no-any-return]


class FroniusOhmpilotUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius Ohmpilots and keep track of seen conditions."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)
    valid_descriptions = OHMPILOT_ENTITY_DESCRIPTIONS

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.solar_net.fronius.current_system_ohmpilot_data()
        return data["ohmpilots"]  # type: ignore[no-any-return]


class FroniusPowerFlowUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius power flow endpoint and keep track of seen conditions."""

    default_interval = timedelta(seconds=10)
    error_interval = timedelta(minutes=3)
    valid_descriptions = POWER_FLOW_ENTITY_DESCRIPTIONS

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.solar_net.fronius.current_power_flow()
        return {SOLAR_NET_ID_POWER_FLOW: data}


class FroniusStorageUpdateCoordinator(FroniusCoordinatorBase):
    """Query Fronius system storage endpoint and keep track of seen conditions."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)
    valid_descriptions = STORAGE_ENTITY_DESCRIPTIONS

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.solar_net.fronius.current_system_storage_data()
        return data["storages"]  # type: ignore[no-any-return]
