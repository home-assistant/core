"""Sensor platform for Grandstream integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import GrandstreamConfigEntry
from .const import DEVICE_TYPE_GNS_NAS, DOMAIN
from .coordinator import GrandstreamCoordinator
from .device import GrandstreamDevice

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GrandstreamSensorEntityDescription(SensorEntityDescription):
    """Describes Grandstream sensor entity."""

    key_path: str | None = None  # For nested data paths like "disks[0].temperature_c"


# Device status sensors
DEVICE_SENSORS: tuple[GrandstreamSensorEntityDescription, ...] = (
    GrandstreamSensorEntityDescription(
        key="phone_status",
        key_path="phone_status",
        translation_key="device_status",
        icon="mdi:account-badge",
    ),
)

# SIP account sensors (multiple accounts supported)
SIP_ACCOUNT_SENSORS: tuple[GrandstreamSensorEntityDescription, ...] = (
    GrandstreamSensorEntityDescription(
        key="sip_registration_status",
        key_path="sip_accounts[{index}].status",
        translation_key="sip_registration_status",
        icon="mdi:phone-check",
    ),
)

# System monitoring sensors
SYSTEM_SENSORS: tuple[GrandstreamSensorEntityDescription, ...] = (
    GrandstreamSensorEntityDescription(
        key="cpu_usage_percent",
        key_path="cpu_usage_percent",
        translation_key="cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chip",
    ),
    GrandstreamSensorEntityDescription(
        key="memory_used_gb",
        key_path="memory_used_gb",
        translation_key="memory_used_gb",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:memory",
    ),
    GrandstreamSensorEntityDescription(
        key="memory_usage_percent",
        key_path="memory_usage_percent",
        translation_key="memory_usage_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:memory",
    ),
    GrandstreamSensorEntityDescription(
        key="system_temperature_c",
        key_path="system_temperature_c",
        translation_key="system_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GrandstreamSensorEntityDescription(
        key="cpu_temperature_c",
        key_path="cpu_temperature_c",
        translation_key="cpu_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GrandstreamSensorEntityDescription(
        key="running_time",
        key_path="running_time",
        translation_key="system_uptime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:clock",
    ),
    GrandstreamSensorEntityDescription(
        key="network_sent_speed",
        key_path="network_sent_bytes_per_sec",
        translation_key="network_upload_speed",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:upload",
    ),
    GrandstreamSensorEntityDescription(
        key="network_received_speed",
        key_path="network_received_bytes_per_sec",
        translation_key="network_download_speed",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:download",
    ),
    GrandstreamSensorEntityDescription(
        key="fan_mode",
        key_path="fan_mode",
        translation_key="fan_mode",
        icon="mdi:fan",
    ),
)

# Fan sensors
FAN_SENSORS: tuple[GrandstreamSensorEntityDescription, ...] = (
    GrandstreamSensorEntityDescription(
        key="fan_status",
        key_path="fans[{index}]",
        translation_key="fan_status",
        icon="mdi:fan",
    ),
)

# Disk sensors
DISK_SENSORS: tuple[GrandstreamSensorEntityDescription, ...] = (
    GrandstreamSensorEntityDescription(
        key="disk_temperature",
        key_path="disks[{index}].temperature_c",
        translation_key="disk_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    GrandstreamSensorEntityDescription(
        key="disk_status",
        key_path="disks[{index}].status",
        translation_key="disk_status",
        icon="mdi:harddisk",
    ),
    GrandstreamSensorEntityDescription(
        key="disk_size",
        key_path="disks[{index}].size_gb",
        translation_key="disk_size",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:harddisk",
    ),
)

# Pool sensors
POOL_SENSORS: tuple[GrandstreamSensorEntityDescription, ...] = (
    GrandstreamSensorEntityDescription(
        key="pool_size",
        key_path="pools[{index}].size_gb",
        translation_key="pool_size",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:database",
    ),
    GrandstreamSensorEntityDescription(
        key="pool_usage",
        key_path="pools[{index}].usage_percent",
        translation_key="pool_usage",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:database",
    ),
    GrandstreamSensorEntityDescription(
        key="pool_status",
        key_path="pools[{index}].status",
        translation_key="pool_status",
        icon="mdi:database",
    ),
)


class GrandstreamSensor(SensorEntity):
    """Base class for Grandstream sensors."""

    entity_description: GrandstreamSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GrandstreamCoordinator,
        device: GrandstreamDevice,
        description: GrandstreamSensorEntityDescription,
        index: int | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self.coordinator = coordinator
        self._device = device
        self.entity_description = description
        self._index = index

        # Set unique ID
        unique_id = f"{device.unique_id}_{description.key}"
        if index is not None:
            unique_id = f"{unique_id}_{index}"
        self._attr_unique_id = unique_id

        # Set device info
        self._attr_device_info = device.device_info

        # Set name based on device name and translation key
        # Note: We're using _attr_has_entity_name = True, so only the translation key will be used

        # Set translation placeholders for indexed entities
        if index is not None:
            self._attr_translation_placeholders = {"index": str(index + 1)}

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and super().available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @staticmethod
    def _get_by_path(data: dict[str, Any], path: str, index: int | None = None):
        """Resolve nested value by path like 'disks[0].temperature_c' or 'fans[0]'."""
        if index is not None and "{index}" in path:
            path = path.replace("{index}", str(index))

        cur = data
        parts = path.split(".")
        for part in parts:
            # Handle list index like key[0]
            while "[" in part and "]" in part:
                base = part[: part.index("[")]
                idx_str = part[part.index("[") + 1 : part.index("]")]
                if base:
                    if isinstance(cur, dict):
                        temp = cur.get(base)
                        if temp is None:
                            return None
                        cur = temp
                    else:
                        return None
                try:
                    idx = int(idx_str)
                except ValueError:
                    return None
                if isinstance(cur, list) and 0 <= idx < len(cur):
                    cur = cur[idx]
                else:
                    return None
                # fully processed this bracketed segment
                if part.endswith("]"):
                    part = ""
                else:
                    part = part[part.index("]") + 1 :]
            if part:
                if isinstance(cur, dict):
                    temp = cur.get(part)
                    if temp is None:
                        return None
                    cur = temp
                else:
                    return None
        return cur


class GrandstreamSystemSensor(GrandstreamSensor):
    """Representation of a Grandstream system sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.entity_description.key_path:
            return None

        return self._get_by_path(
            self.coordinator.data, self.entity_description.key_path
        )


class GrandstreamDeviceSensor(GrandstreamSensor):
    """Representation of a Grandstream device sensor."""

    def _get_api_instance(self):
        """Get API instance from hass.data."""

        if DOMAIN in self.hass.data and hasattr(self._device, "config_entry_id"):
            entry_data = self.hass.data[DOMAIN].get(self._device.config_entry_id)
            if entry_data and "api" in entry_data:
                return entry_data["api"]
        return None

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        # For phone_status sensor, check connection state first
        if self.entity_description.key == "phone_status":
            api = self._get_api_instance()
            if api:
                # Return connection status key if there's any issue
                # Translation keys: ha_control_disabled, offline, account_locked, auth_failed
                if (
                    hasattr(api, "is_ha_control_enabled")
                    and not api.is_ha_control_enabled
                ):
                    return "ha_control_disabled"
                if hasattr(api, "is_online") and not api.is_online:
                    return "offline"
                if hasattr(api, "is_account_locked") and api.is_account_locked:
                    return "account_locked"
                if hasattr(api, "is_authenticated") and not api.is_authenticated:
                    return "auth_failed"

        if self.entity_description.key_path and self._index is not None:
            value = self._get_by_path(
                self.coordinator.data, self.entity_description.key_path, self._index
            )
        elif self.entity_description.key_path:
            value = self._get_by_path(
                self.coordinator.data, self.entity_description.key_path
            )
        else:
            return None

        return value


class GrandstreamSipAccountSensor(GrandstreamSensor):
    """Representation of a Grandstream SIP account sensor."""

    def __init__(
        self,
        coordinator: GrandstreamCoordinator,
        device: GrandstreamDevice,
        description: GrandstreamSensorEntityDescription,
        account_id: str,
    ) -> None:
        """Initialize the SIP account sensor."""
        # Call parent init with index=None (will be determined dynamically)
        super().__init__(coordinator, device, description, index=None)

        # Store account_id for dynamic lookup
        self._account_id = account_id

        # Override unique ID to use account_id instead of index
        self._attr_unique_id = f"{device.unique_id}_{description.key}_{account_id}"

        # Set translation placeholders for account ID
        self._attr_translation_placeholders = {"account_id": account_id}

    def _find_account_index(self) -> int | None:
        """Find the current index of this account in the accounts list."""
        sip_accounts = self.coordinator.data.get("sip_accounts", [])
        for idx, account in enumerate(sip_accounts):
            if isinstance(account, dict) and account.get("id") == self._account_id:
                return idx
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Check if coordinator is available
        if not self.coordinator.last_update_success:
            return False

        # Check if this account still exists by ID
        return self._find_account_index() is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.entity_description.key_path:
            return None

        # Find current index of this account
        current_index = self._find_account_index()
        if current_index is None:
            return None

        return self._get_by_path(
            self.coordinator.data, self.entity_description.key_path, current_index
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GrandstreamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device = hass.data[DOMAIN][config_entry.entry_id]["device"]

    entities: list[GrandstreamSensor] = []

    # Track created SIP account sensors by account ID
    created_sip_sensors: set[str] = set()

    if getattr(device, "device_type", None) == DEVICE_TYPE_GNS_NAS:
        # Add system sensors
        entities.extend(
            GrandstreamSystemSensor(coordinator, device, description)
            for description in SYSTEM_SENSORS
        )

        # Add fan sensors (multiple)
        fan_count = max(len(coordinator.data.get("fans", [])), 1)
        entities.extend(
            GrandstreamDeviceSensor(coordinator, device, description, idx)
            for idx in range(fan_count)
            for description in FAN_SENSORS
        )

        # Add disk sensors (multiple)
        disk_count = max(len(coordinator.data.get("disks", [])), 1)
        entities.extend(
            GrandstreamDeviceSensor(coordinator, device, description, idx)
            for idx in range(disk_count)
            for description in DISK_SENSORS
        )

        # Add pool sensors (multiple)
        pool_count = max(len(coordinator.data.get("pools", [])), 1)
        entities.extend(
            GrandstreamDeviceSensor(coordinator, device, description, idx)
            for idx in range(pool_count)
            for description in POOL_SENSORS
        )
    else:
        # Add phone device sensors
        entities.extend(
            GrandstreamDeviceSensor(coordinator, device, description)
            for description in DEVICE_SENSORS
        )

        # Add SIP account sensors (only if accounts exist)
        # Track by account ID instead of index
        sip_accounts = coordinator.data.get("sip_accounts", [])
        for account in sip_accounts:
            if isinstance(account, dict):
                account_id = account.get("id", "")
                if account_id:
                    entities.extend(
                        GrandstreamSipAccountSensor(
                            coordinator, device, description, account_id
                        )
                        for description in SIP_ACCOUNT_SENSORS
                    )
                    created_sip_sensors.add(account_id)

        # Add listener to dynamically add new SIP account sensors
        @callback
        def _async_add_sip_sensors() -> None:
            """Add new SIP account sensors when accounts are added."""
            sip_accounts = coordinator.data.get("sip_accounts", [])
            new_entities: list[GrandstreamSipAccountSensor] = []

            for account in sip_accounts:
                if isinstance(account, dict):
                    account_id = account.get("id", "")
                    if account_id and account_id not in created_sip_sensors:
                        new_entities.extend(
                            GrandstreamSipAccountSensor(
                                coordinator, device, description, account_id
                            )
                            for description in SIP_ACCOUNT_SENSORS
                        )
                        created_sip_sensors.add(account_id)

            if new_entities:
                async_add_entities(new_entities)

        # Register listener
        config_entry.async_on_unload(
            coordinator.async_add_listener(_async_add_sip_sensors)
        )

    async_add_entities(entities)
