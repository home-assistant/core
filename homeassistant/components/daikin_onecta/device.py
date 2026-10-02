"""Represent Daikin Onecta gateway devices."""

import logging
from typing import Any

from daikin_onecta.models import GatewayDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

from .const import DOMAIN
from .daikin_api import DaikinApi

_LOGGER = logging.getLogger(__name__)


class DaikinOnectaDevice:
    """Class to represent and control one Daikin Onecta Device."""

    def __init__(self, device: GatewayDevice, apiInstance: DaikinApi) -> None:
        """Initialize a new Daikin Onecta Device."""
        self.api = apiInstance
        # get name from climateControl
        self.device = device
        self.id: str = device.id
        self.name: str = device.device_model

        for management_point in device.management_points_by_type("climateControl"):
            if management_point.name is not None and management_point.name.value:
                self.name = management_point.name.value

        # Populated by async_register_ha_device() before any entity platform is set
        # up. Sub-entities (per-management-point devices in sensor/water_heater/
        # select/binary_sensor/switch/update) use this as via_device_id to link back
        # to this gateway device: the older via_device=(DOMAIN, identifier) form is
        # deprecated because identifiers are no longer guaranteed globally unique.
        self.ha_device_id: str | None = None

        _LOGGER.info(
            "Initialized Daikin Onecta Device '%s' (id %s)", self.name, self.id
        )

    @property
    def available(self) -> bool:
        """Return whether the device is connected to the Daikin cloud."""
        return self.device.available

    def management_point(self, embedded_id: str):
        """Return a management point by embedded id."""
        return self.device.management_point(embedded_id)

    def fill_device_info(self, device_info: DeviceInfo, embedded_id: str) -> None:
        """Fill Home Assistant device information from an embedded management point ID."""
        device_info["manufacturer"] = "Daikin"
        point = self.device.management_point(embedded_id)
        if point is None:
            return
        if point.eeprom_version is not None:
            device_info["sw_version"] = point.eeprom_version.value
        if point.model_info is not None:
            device_info["model"] = point.model_info.value
        if point.firmware_version is not None:
            device_info["sw_version"] = point.firmware_version.value
        if point.serial_number is not None:
            device_info["serial_number"] = point.serial_number.value
        if point.software_version is not None:
            device_info["sw_version"] = point.software_version.value

    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        gateway = self.device.management_point_by_type("gateway")
        mac_address = (
            gateway.characteristic("macAddress") if gateway is not None else None
        )
        connections = set()
        if mac_address is not None and mac_address.value:
            connections.add((CONNECTION_NETWORK_MAC, mac_address.value))

        info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.id)
            },
            connections=connections,
            name=self.name,
            model_id=self.device.device_model,
        )

        self.fill_device_info(info, "gateway")
        return info

    def async_register_ha_device(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Eagerly create/update this device in the device registry.

        Called once from the coordinator, before any entity platform is set up
        (platforms are forwarded concurrently, so entity __init__ order across
        platforms can't be relied on). This guarantees self.ha_device_id is
        already populated by the time any platform builds a sub-device's
        DeviceInfo with via_device_id=self.ha_device_id.
        """
        device_registry = dr.async_get(hass)
        entry = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            **self.device_info(),
        )
        self.ha_device_id = entry.id

    def set_device_data(self, device: GatewayDevice) -> None:
        """Overwrite the typed and compatibility data for this device."""
        self.device = device
        _LOGGER.debug(
            "Device '%s' received new data from the Daikin cloud, isCloudConnectionUp '%s'",
            self.name,
            self.available,
        )

    async def patch(
        self,
        id: str,
        embeddedId: str,
        dataPoint: str,
        dataPointPath: str | None,
        value: Any,
    ) -> bool:
        """Patch a characteristic."""
        return await self.api.patch_characteristic(
            id,
            embeddedId,
            dataPoint,
            value,
            path=dataPointPath,
        )

    async def post(self, id: str, embeddedId: str, dataPoint: str, value: Any) -> bool:
        """POST a management-point resource."""
        return await self.api.post_management_point(id, embeddedId, dataPoint, value)

    async def put(
        self, id: str, embeddedId: str, dataPoint: str, value: Any = None
    ) -> bool:
        """PUT a management-point resource."""
        return await self.api.put_management_point(id, embeddedId, dataPoint, value)


def migrate_legacy_subdevice_identifiers(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    devices: dict[str, DaikinOnectaDevice],
) -> None:
    """Migrate type-based subdevice identifiers to embedded management-point IDs.

    Legacy versions could represent only one management point of a given type.
    Preserve that device registry entry for the first matching point, while
    later same-type points receive their own identifiers when entities are set
    up.
    """
    device_registry = dr.async_get(hass)
    for device in devices.values():
        management_points_by_type: dict[str, list[Any]] = {}
        for management_point in device.device.management_points:
            management_points_by_type.setdefault(
                management_point.management_point_type, []
            ).append(management_point)

        for (
            management_point_type,
            management_points,
        ) in management_points_by_type.items():
            legacy_identifier = (DOMAIN, device.id + management_point_type)
            registry_entry = device_registry.async_get_device_by_identifier(
                legacy_identifier, config_entry.entry_id
            )
            if (
                registry_entry is None
                or config_entry.entry_id != registry_entry.config_entry_id
            ):
                continue

            embedded_identifier = (DOMAIN, device.id + management_points[0].embedded_id)
            identifiers = set(registry_entry.identifiers)
            identifiers.discard(legacy_identifier)
            identifiers.add(embedded_identifier)
            device_registry.async_update_device(
                registry_entry.id, new_identifiers=identifiers
            )


def _migrate_type_based_entity_unique_id(
    device: DaikinOnectaDevice,
    unique_id: str,
    points_by_type: dict[str, list[Any]],
) -> str | None:
    """Return an embedded-ID unique ID for a type-based legacy ID."""
    for management_point_type, points in points_by_type.items():
        old_prefix = f"{device.id}_{management_point_type}_"
        if unique_id.startswith(old_prefix):
            return f"{device.id}_{points[0].embedded_id}_{unique_id.removeprefix(old_prefix)}"
    return None


def _legacy_entity_unique_id(
    device: DaikinOnectaDevice,
    entry: Any,
    points_by_type: dict[str, list[Any]],
) -> str | None:
    """Return the embedded-ID equivalent of a legacy entity unique ID."""
    if entry.domain in {"binary_sensor", "select", "switch", "update"}:
        return _migrate_type_based_entity_unique_id(
            device, entry.unique_id, points_by_type
        )

    if entry.domain == "climate":
        climate_points = points_by_type.get("climateControl", [])
        old_prefix = f"{device.id}_"
        if climate_points and entry.unique_id.startswith(old_prefix):
            return f"{device.id}_{climate_points[-1].embedded_id}_{entry.unique_id.removeprefix(old_prefix)}"

    if entry.domain == "water_heater" and entry.unique_id == device.id:
        for management_point_type in (
            "domesticHotWaterTank",
            "domesticHotWaterFlowThrough",
        ):
            if points := points_by_type.get(management_point_type):
                return f"{device.id}_{points[0].embedded_id}"

    return None


def migrate_legacy_entity_unique_ids(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    devices: dict[str, DaikinOnectaDevice],
) -> None:
    """Migrate per-management-point entity IDs to use embedded IDs.

    Management-point types are not unique on multi-zone systems.  Keep the
    existing entity registry entry for the first matching point, matching the
    legacy platform setup behavior, so users retain their entity IDs, history,
    and customizations.
    """
    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)

    for device in devices.values():
        points_by_type: dict[str, list[Any]] = {}
        for management_point in device.device.management_points:
            points_by_type.setdefault(
                management_point.management_point_type, []
            ).append(management_point)

        for entry in entries:
            if entry.platform != DOMAIN:
                continue
            new_unique_id = _legacy_entity_unique_id(device, entry, points_by_type)

            if (
                new_unique_id is None
                or entity_registry.async_get_entity_id(
                    entry.domain, DOMAIN, new_unique_id
                )
                is not None
            ):
                continue
            entity_registry.async_update_entity(
                entry.entity_id, new_unique_id=new_unique_id
            )
