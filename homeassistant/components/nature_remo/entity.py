"""Base entities for the Nature Remo integration."""

from typing import override

from aionatureremo import Appliance, Device

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NatureRemoCoordinator


def build_remo_device_info(device: Device) -> DeviceInfo:
    """Build device-registry info for a Remo hardware device."""
    model, _, sw_version = device.firmware_version.partition("/")
    device_info = DeviceInfo(
        identifiers={(DOMAIN, device.id)},
        name=device.name,
        manufacturer="Nature",
        model=model or None,
        sw_version=sw_version or None,
        serial_number=device.serial_number,
        configuration_url="https://home.nature.global/",
    )
    if device.mac_address:
        device_info["connections"] = {(CONNECTION_NETWORK_MAC, device.mac_address)}
    return device_info


def build_appliance_device_info(
    appliance: Appliance, via_device_id: str | None = None
) -> DeviceInfo:
    """Build device-registry info for an appliance behind a Remo.

    ``via_device_id`` is the registry id of the hub, which only the caller
    that just registered that hub knows; entities leave it out and attach
    to the device the setup registration already linked.
    """
    model = appliance.model
    device_info = DeviceInfo(
        identifiers={(DOMAIN, appliance.id)},
        name=appliance.nickname,
        manufacturer=model.manufacturer if model else None,
        model=(model.name or model.remote_name) if model else None,
    )
    if via_device_id:
        device_info["via_device_id"] = via_device_id
    return device_info


class NatureRemoDeviceEntity(CoordinatorEntity[NatureRemoCoordinator]):
    """An entity belonging to a Nature Remo hardware device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NatureRemoCoordinator, device_id: str) -> None:
        """Initialize with device registry info for the Remo hardware."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_device_info = build_remo_device_info(
            coordinator.data.devices[device_id]
        )

    @property
    def device(self) -> Device:
        """Return the current device data."""
        return self.coordinator.data.devices[self._device_id]

    @property
    @override
    def available(self) -> bool:
        """Unavailable when the device disappears or reports itself offline.

        ``online`` is three-valued: only newer firmware (Nature-2W3 /
        Remo 2.x / Remo-E-lite) reports it, so None means "not reported"
        and must stay available. An explicit False means the hub is
        unreachable and its last readings are stale.
        """
        return (
            super().available
            and self._device_id in self.coordinator.data.devices
            and self.device.online is not False
        )


class NatureRemoApplianceEntity(CoordinatorEntity[NatureRemoCoordinator]):
    """An entity belonging to an appliance controlled through a Remo."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NatureRemoCoordinator, appliance_id: str) -> None:
        """Initialize with an appliance device linked to its Remo."""
        super().__init__(coordinator)
        self._appliance_id = appliance_id
        self._attr_device_info = build_appliance_device_info(
            coordinator.data.appliances[appliance_id]
        )

    @property
    def appliance(self) -> Appliance:
        """Return the current appliance data."""
        return self.coordinator.data.appliances[self._appliance_id]

    @property
    @override
    def available(self) -> bool:
        """Unavailable when the appliance, or the hub reporting it, is gone.

        The appliance is only reachable through its Remo, so a hub that
        dropped out of the account or reports itself offline leaves the
        readings the cloud still serves stale. ``online`` is three-valued:
        older firmware never reports it, so only an explicit False counts
        as offline.
        """
        if (
            not super().available
            or self._appliance_id not in self.coordinator.data.appliances
        ):
            return False
        hub_id = self.appliance.device_id
        hub = self.coordinator.data.devices.get(hub_id) if hub_id else None
        return hub is not None and hub.online is not False
