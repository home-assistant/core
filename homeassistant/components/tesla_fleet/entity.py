"""Tesla Fleet parent entity class."""

from abc import abstractmethod
from typing import Any, override

from tesla_fleet_api.const import Scope, VehicleDataEndpoint
from tesla_fleet_api.tesla.energysite import EnergySite
from tesla_fleet_api.tesla.vehicle.fleet import VehicleFleet

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    TeslaFleetEnergySiteHistoryCoordinator,
    TeslaFleetEnergySiteInfoCoordinator,
    TeslaFleetEnergySiteLiveCoordinator,
    TeslaFleetVehicleDataCoordinator,
)
from .helpers import wake_up_vehicle
from .models import TeslaFleetEnergyData, TeslaFleetVehicleData

# Location data is returned within the drive_state group, so requesting a
# drive_state field also requires the location_data endpoint.
_VEHICLE_ENDPOINT_BY_PREFIX: tuple[tuple[str, frozenset[VehicleDataEndpoint]], ...] = (
    ("charge_state", frozenset({VehicleDataEndpoint.CHARGE_STATE})),
    ("climate_state", frozenset({VehicleDataEndpoint.CLIMATE_STATE})),
    (
        "drive_state",
        frozenset({VehicleDataEndpoint.DRIVE_STATE, VehicleDataEndpoint.LOCATION_DATA}),
    ),
    ("vehicle_state", frozenset({VehicleDataEndpoint.VEHICLE_STATE})),
    ("vehicle_config", frozenset({VehicleDataEndpoint.VEHICLE_CONFIG})),
)


def endpoints_for_key(key: str) -> frozenset[VehicleDataEndpoint]:
    """Return the vehicle data endpoints a flattened data key is sourced from."""
    for prefix, endpoints in _VEHICLE_ENDPOINT_BY_PREFIX:
        if key.startswith(prefix):
            return endpoints
    return frozenset()


class TeslaFleetEntity[_ApiT: VehicleFleet | EnergySite](
    CoordinatorEntity[
        TeslaFleetVehicleDataCoordinator
        | TeslaFleetEnergySiteLiveCoordinator
        | TeslaFleetEnergySiteHistoryCoordinator
        | TeslaFleetEnergySiteInfoCoordinator
    ]
):
    """Parent class for all TeslaFleet entities."""

    _attr_has_entity_name = True
    read_only: bool
    scoped: bool
    api: _ApiT

    def __init__(
        self,
        coordinator: TeslaFleetVehicleDataCoordinator
        | TeslaFleetEnergySiteLiveCoordinator
        | TeslaFleetEnergySiteHistoryCoordinator
        | TeslaFleetEnergySiteInfoCoordinator,
        api: _ApiT,
        key: str,
        context: Any = None,
    ) -> None:
        """Initialize common aspects of a TeslaFleet entity."""
        super().__init__(coordinator, context)
        self.api = api
        self.key = key
        self._attr_translation_key = self.key
        self._async_update_attrs()

    @property
    @override
    def available(self) -> bool:
        """Return if sensor is available."""
        return self.coordinator.last_update_success and self._attr_available

    @property
    def _value(self) -> Any | None:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(self.key)

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(key, default)

    def get_number(self, key: str, default: float) -> float:
        """Return a specific number from coordinator data."""
        if isinstance(value := self.coordinator.data.get(key), (int, float)):
            return value
        return default

    @property
    def is_none(self) -> bool:
        """Return if the value is a literal None."""
        return self.get(self.key, False) is None

    @property
    def has(self) -> bool:
        """Return True if a specific value is in coordinator data."""
        return self.key in self.coordinator.data

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        self.async_write_ha_state()

    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

    def raise_for_read_only(self, scope: Scope) -> None:
        """Raise an error if a scope is not available."""
        if not self.scoped:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"missing_scope_{scope.name.lower()}",
            )


class TeslaFleetVehicleEntity(TeslaFleetEntity[VehicleFleet]):
    """Parent class for TeslaFleet Vehicle entities."""

    _last_update: int = 0
    # Vehicle data endpoints this entity needs polled. None derives them from
    # the flattened key prefix; set explicitly when the key does not encode it.
    _endpoints: frozenset[VehicleDataEndpoint] | None = None

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tesla Fleet entity."""

        self._attr_unique_id = f"{data.vin}-{key}"
        self.vehicle = data

        self._attr_device_info = data.device
        endpoints = (
            self._endpoints if self._endpoints is not None else endpoints_for_key(key)
        )
        super().__init__(data.coordinator, data.api, key, endpoints)

    @property
    @override
    def _value(self) -> Any | None:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(self.key)

    async def wake_up_if_asleep(self) -> None:
        """Wake up the vehicle if its asleep."""
        await wake_up_vehicle(self.vehicle)


class TeslaFleetEnergyLiveEntity(TeslaFleetEntity[EnergySite]):
    """Parent class for TeslaFleet Energy Site Live entities."""

    def __init__(
        self,
        data: TeslaFleetEnergyData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tesla Fleet Energy Site Live entity."""
        self._attr_unique_id = f"{data.id}-{key}"
        self._attr_device_info = data.device

        super().__init__(data.live_coordinator, data.api, key)


class TeslaFleetEnergyHistoryEntity(TeslaFleetEntity[EnergySite]):
    """Parent class for TeslaFleet Energy Site History entities."""

    def __init__(
        self,
        data: TeslaFleetEnergyData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tesla Fleet Energy Site History entity."""
        self._attr_unique_id = f"{data.id}-{key}"
        self._attr_device_info = data.device

        super().__init__(data.history_coordinator, data.api, key)


class TeslaFleetEnergyInfoEntity(TeslaFleetEntity[EnergySite]):
    """Parent class for TeslaFleet Energy Site Info entities."""

    def __init__(
        self,
        data: TeslaFleetEnergyData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tesla Fleet Energy Site Info entity."""
        self._attr_unique_id = f"{data.id}-{key}"
        self._attr_device_info = data.device

        super().__init__(data.info_coordinator, data.api, key)


class TeslaFleetWallConnectorEntity(
    TeslaFleetEntity[EnergySite], CoordinatorEntity[TeslaFleetEnergySiteLiveCoordinator]
):
    """Parent class for Tesla Fleet Wall Connector entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        data: TeslaFleetEnergyData,
        din: str,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tesla Fleet entity."""
        self.din = din
        self._attr_unique_id = f"{data.id}-{din}-{key}"

        # Find the model from the info coordinator
        model: str | None = None
        for wc in data.info_coordinator.data.get("components_wall_connectors", []):
            if wc["din"] == din:
                model = wc.get("part_name")
                break

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, din)},
            manufacturer="Tesla",
            name="Wall Connector",
            via_device_id=dr.async_get_device_id_by_identifier(
                data.live_coordinator.hass,
                (DOMAIN, str(data.id)),
                config_entry_id=data.live_coordinator.config_entry.entry_id,
            ),
            serial_number=din.rsplit("-", maxsplit=1)[-1],
            model=model,
        )

        super().__init__(data.live_coordinator, data.api, key)

    @property
    @override
    def _value(self) -> int:
        """Return a specific wall connector value from coordinator data."""
        return (
            self.coordinator.data.get("wall_connectors", {})
            .get(self.din, {})
            .get(self.key)
        )
