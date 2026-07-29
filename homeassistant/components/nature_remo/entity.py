"""Base entities for the Nature Remo integration."""

from aionatureremo import Appliance, Device

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NatureRemoCoordinator


def build_remo_device_info(device: Device) -> DeviceInfo:
    """Build device-registry info for a Remo hardware device (spec 5.4).

    Shared by the entity base and the eager device registration in
    ``async_setup_entry`` so both describe the hub identically.
    """
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


def build_appliance_device_info(appliance: Appliance) -> DeviceInfo:
    """Build device-registry info for an appliance behind a Remo (spec 5.4).

    Shared by the entity base and the per-poll device registration in
    ``async_setup_entry``: registering from the same builder is what lets a
    nickname edited in the Nature app reach the device registry, and keeps
    the two descriptions from drifting apart.
    """
    model = appliance.model
    device_info = DeviceInfo(
        identifiers={(DOMAIN, appliance.id)},
        name=appliance.nickname,
        manufacturer=model.manufacturer if model else None,
        model=(model.name or model.remote_name) if model else None,
    )
    if appliance.device_id:
        device_info["via_device"] = (DOMAIN, appliance.device_id)
    return device_info


class NatureRemoDeviceEntity(CoordinatorEntity[NatureRemoCoordinator]):
    """An entity belonging to a Nature Remo hardware device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NatureRemoCoordinator, device_id: str) -> None:
        """Initialize with device registry info for the Remo hardware."""
        super().__init__(coordinator)
        self._device_id = device_id
        device = coordinator.data.devices[device_id]
        self._last_device = device
        self._attr_device_info = build_remo_device_info(device)

    @property
    def device(self) -> Device:
        """Return the current device data, or the last one seen.

        A hub can vanish from a poll (removed from the account, or a
        truncated response) while service calls and state writes still reach
        the entity; falling back to the last known snapshot keeps those paths
        from raising a bare KeyError. ``available`` is what reports the hub
        as gone.
        """
        device = self.coordinator.data.devices.get(self._device_id)
        if device is not None:
            self._last_device = device
        return self._last_device

    @property
    def available(self) -> bool:
        """Unavailable when the device disappears or reports itself offline.

        ``online`` is three-valued: only newer firmware (Nature-2W3 /
        Remo 2.x / Remo-E-lite) reports it, so None means "not reported"
        and must stay available. An explicit False means the hub is
        unreachable and its last readings are stale.
        """
        if (
            not super().available
            or self._device_id not in self.coordinator.data.devices
        ):
            return False
        return self.device.online is not False


class NatureRemoApplianceEntity(CoordinatorEntity[NatureRemoCoordinator]):
    """An entity belonging to an appliance controlled through a Remo."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NatureRemoCoordinator, appliance_id: str) -> None:
        """Initialize with an appliance device linked to its Remo."""
        super().__init__(coordinator)
        self._appliance_id = appliance_id
        appliance = coordinator.data.appliances[appliance_id]
        self._last_appliance = appliance
        self._attr_device_info = build_appliance_device_info(appliance)

    @property
    def appliance(self) -> Appliance:
        """Return the current appliance data, or the last one seen.

        An appliance can vanish from a poll (deleted in the Nature app, or
        a truncated response), and state writes and service calls still
        reach the entity afterwards; falling back to the last known
        snapshot keeps those paths from raising a bare KeyError.
        ``available`` is what reports the appliance as gone.
        """
        appliance = self.coordinator.data.appliances.get(self._appliance_id)
        if appliance is not None:
            self._last_appliance = appliance
        return self._last_appliance

    @property
    def available(self) -> bool:
        """Unavailable when the appliance disappears from the account."""
        return (
            super().available and self._appliance_id in self.coordinator.data.appliances
        )
