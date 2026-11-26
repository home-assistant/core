"""Base entity for Zonneplan."""

from pyzonneplan import Battery, ChargePoint, Contract

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    ZonneplanBatteryControlCoordinator,
    ZonneplanBatteryCoordinator,
    ZonneplanBatterySettingsCoordinator,
    ZonneplanChargePointCoordinator,
    ZonneplanCoordinator,
)


class ZonneplanEntity(CoordinatorEntity[ZonneplanCoordinator]):
    """Base entity for Zonneplan."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ZonneplanCoordinator, entity_description: EntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.data.account.user_account.uuid}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Zonneplan",
            entry_type=DeviceEntryType.SERVICE,
        )


class ZonneplanContractEntity[
    _CoordinatorT: ZonneplanBatteryCoordinator
    | ZonneplanBatteryControlCoordinator
    | ZonneplanChargePointCoordinator
    | ZonneplanBatterySettingsCoordinator
](CoordinatorEntity[_CoordinatorT]):
    """Base entity on the device of a Zonneplan contract, like a home battery."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: _CoordinatorT,
        contract_uuid: str,
        contract: Contract,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._contract_uuid = contract_uuid
        self._attr_unique_id = f"{contract_uuid}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, contract_uuid)},
            name=contract.label,
            manufacturer="Zonneplan",
            model=contract.model_name,
            serial_number=contract.serial_number,
        )


class ZonneplanBatteryEntity(ZonneplanContractEntity[ZonneplanBatteryCoordinator]):
    """Base entity for a Zonneplan home battery."""

    def __init__(
        self,
        coordinator: ZonneplanBatteryCoordinator,
        contract_uuid: str,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            contract_uuid,
            coordinator.data[contract_uuid].battery.contract,
            entity_description,
        )

    @property
    def battery(self) -> Battery:
        """Return the battery of this entity."""
        return self.coordinator.data[self._contract_uuid].battery


class ZonneplanChargePointEntity(
    ZonneplanContractEntity[ZonneplanChargePointCoordinator]
):
    """Base entity for a Zonneplan charge point."""

    def __init__(
        self,
        coordinator: ZonneplanChargePointCoordinator,
        contract_uuid: str,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            contract_uuid,
            coordinator.data[contract_uuid],
            entity_description,
        )

    @property
    def charge_point(self) -> ChargePoint:
        """Return the charge point of this entity."""
        return self.coordinator.data[self._contract_uuid]
