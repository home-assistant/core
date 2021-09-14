"""DataUpdateCoordinators for the Fronius integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Dict, TypeVar

from pyfronius import Fronius, FroniusError

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
from .descriptions import (
    INVERTER_ENTITY_DESCRIPTIONS,
    LOGGER_ENTITY_DESCRIPTIONS,
    METER_ENTITY_DESCRIPTIONS,
    POWER_FLOW_ENTITY_DESCRIPTIONS,
    STORAGE_ENTITY_DESCRIPTIONS,
)

if TYPE_CHECKING:
    from . import FroniusSolarNet
    from .sensor import _FroniusSensorEntity

    FroniusEntityType = TypeVar("FroniusEntityType", bound=_FroniusSensorEntity)


class _FroniusUpdateCoordinator(
    DataUpdateCoordinator[Dict[SolarNetId, Dict[str, Any]]]
):
    """Query Fronius endpoint and keep track of seen conditions."""

    valid_descriptions: Mapping[str, SensorEntityDescription]

    def __init__(self, *args: Any, solar_net: FroniusSolarNet, **kwargs: Any) -> None:
        """Set up the _FroniusUpdateCoordinator class."""
        self.lock = solar_net.coordinator_lock
        self.fronius: Fronius = solar_net.fronius
        self.solar_net_device_id = solar_net.solar_net_device_id
        # unregistered_keys are used to create entities in platform module
        self.unregistered_keys: dict[SolarNetId, set[str]] = {}
        super().__init__(*args, **kwargs)

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        raise NotImplementedError("Fronius update method not implemented")

    async def _async_update_data(self) -> dict[SolarNetId, Any]:
        """Fetch the latest data from the source."""
        async with self.lock:
            try:
                data = await self._update_method()
            except FroniusError as err:
                raise UpdateFailed(err) from err

            for solar_net_id in data:
                if solar_net_id not in self.unregistered_keys:
                    # id seen for the first time
                    self.unregistered_keys[solar_net_id] = set(self.valid_descriptions)
            return data

    @callback
    def add_entities_for_seen_keys(
        self,
        async_add_entities: AddEntitiesCallback,
        entity_constructor: type[FroniusEntityType],
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
                    new_entities.append(
                        entity_constructor(
                            self, self.valid_descriptions[key], solar_net_id
                        )
                    )
                    self.unregistered_keys[solar_net_id].remove(key)
            if new_entities:
                async_add_entities(new_entities)

        _add_entities_for_unregistered_keys()
        self.async_add_listener(_add_entities_for_unregistered_keys)


class FroniusInverterUpdateCoordinator(_FroniusUpdateCoordinator):
    """Query Fronius device inverter endpoint and keep track of seen conditions."""

    valid_descriptions = INVERTER_ENTITY_DESCRIPTIONS

    def __init__(
        self, *args: Any, inverter_info: FroniusDeviceInfo, **kwargs: Any
    ) -> None:
        """Set up a Fronius inverter device scope coordinator."""
        super().__init__(*args, **kwargs)
        self.inverter_info = inverter_info

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.fronius.current_inverter_data(self.inverter_info.solar_net_id)
        # wrap a single devices data in a dict with solar_net_id key for
        # _FroniusUpdateCoordinator _async_update_data and add_entities_for_seen_keys
        return {self.inverter_info.solar_net_id: data}


class FroniusLoggerUpdateCoordinator(_FroniusUpdateCoordinator):
    """Query Fronius logger info endpoint and keep track of seen conditions."""

    valid_descriptions = LOGGER_ENTITY_DESCRIPTIONS

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.fronius.current_logger_info()
        return {SOLAR_NET_ID_SYSTEM: data}


class FroniusMeterUpdateCoordinator(_FroniusUpdateCoordinator):
    """Query Fronius system meter endpoint and keep track of seen conditions."""

    valid_descriptions = METER_ENTITY_DESCRIPTIONS

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.fronius.current_system_meter_data()
        return data["meters"]  # type: ignore[no-any-return]


class FroniusPowerFlowUpdateCoordinator(_FroniusUpdateCoordinator):
    """Query Fronius power flow endpoint and keep track of seen conditions."""

    valid_descriptions = POWER_FLOW_ENTITY_DESCRIPTIONS

    def __init__(
        self, *args: Any, power_flow_info: FroniusDeviceInfo, **kwargs: Any
    ) -> None:
        """Set up a Fronius power flow coordinator."""
        super().__init__(*args, **kwargs)
        self.power_flow_info = power_flow_info

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.fronius.current_power_flow()
        return {SOLAR_NET_ID_POWER_FLOW: data}


class FroniusStorageUpdateCoordinator(_FroniusUpdateCoordinator):
    """Query Fronius system storage endpoint and keep track of seen conditions."""

    valid_descriptions = STORAGE_ENTITY_DESCRIPTIONS

    async def _update_method(self) -> dict[SolarNetId, Any]:
        """Return data per solar net id from pyfronius."""
        data = await self.fronius.current_system_storage_data()
        return data["storages"]  # type: ignore[no-any-return]
