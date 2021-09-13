"""DataUpdateCoordinators for the Fronius integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Mapping

from pyfronius import Fronius, FroniusError

from homeassistant.core import callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import SOLAR_NET_ID_POWER_FLOW, FroniusDeviceInfo, SolarNetId
from .descriptions import (
    INVERTER_ENTITY_DESCRIPTIONS,
    METER_ENTITY_DESCRIPTIONS,
    POWER_FLOW_ENTITY_DESCRIPTIONS,
    STORAGE_ENTITY_DESCRIPTIONS,
)

if TYPE_CHECKING:
    from . import FroniusSolarNet


class _FroniusUpdateCoordinator(
    DataUpdateCoordinator[Dict[SolarNetId, Dict[str, Any]]]
):
    """Query Fronius endpoint and keep track of seen conditions."""

    valid_descriptions: Mapping[str, EntityDescription]

    def __init__(self, *args: Any, solar_net: FroniusSolarNet, **kwargs: Any) -> None:
        """Set up the _FroniusUpdateCoordinator class."""
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
        try:
            data = await self._update_method()
        except FroniusError as err:
            raise UpdateFailed from err

        for solar_net_id in data:
            if solar_net_id not in self.unregistered_keys:
                # id seen for the first time
                self.unregistered_keys[solar_net_id] = set(self.valid_descriptions)
        return data

    @callback
    def add_entities_for_seen_keys(
        self,
        async_add_entities: AddEntitiesCallback,
        entity_constructor: type[FroniusEntity],
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


class FroniusEntity(CoordinatorEntity):
    """Defines a Fronius coordinator entity."""

    def __init__(
        self,
        coordinator: _FroniusUpdateCoordinator,
        entity_description: EntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.solar_net_id = solar_net_id

    @property
    def _device_data(self) -> dict[str, Any]:
        return self.coordinator.data[self.solar_net_id]  # type: ignore[no-any-return]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_native_value = self._device_data[self.entity_description.key][
                "value"
            ]
        except KeyError:
            return
        self.async_write_ha_state()
