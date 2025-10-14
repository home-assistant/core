"""Binary sensor for Shelly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from aioshelly.block_device import Block
from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_PLATFORM,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_SLEEP_PERIOD, MODEL_FRANKEVER_WATER_VALVE
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    BlockEntityDescription,
    RestEntityDescription,
    RpcEntityDescription,
    ShellyBlockAttributeEntity,
    ShellyRestAttributeEntity,
    ShellyRpcAttributeEntity,
    ShellySleepingBlockAttributeEntity,
    ShellySleepingRpcAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rest,
    async_setup_entry_rpc,
)
from .utils import (
    async_remove_orphaned_entities,
    get_block_channel_name,
    get_blu_trv_device_info,
    get_device_entry_gen,
    get_rpc_channel_name,
    is_block_momentary_input,
    is_rpc_momentary_input,
    is_view_for_platform,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BlockBinarySensorDescription(
    BlockEntityDescription, BinarySensorEntityDescription
):
    """Class to describe a BLOCK binary sensor."""


@dataclass(frozen=True, kw_only=True)
class RpcBinarySensorDescription(RpcEntityDescription, BinarySensorEntityDescription):
    """Class to describe a RPC binary sensor."""


@dataclass(frozen=True, kw_only=True)
class RestBinarySensorDescription(RestEntityDescription, BinarySensorEntityDescription):
    """Class to describe a REST binary sensor."""


class RpcBinarySensor(ShellyRpcAttributeEntity, BinarySensorEntity):
    """Represent a RPC binary sensor entity."""

    entity_description: RpcBinarySensorDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcBinarySensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, key, attribute, description)

        if description.role != "generic":
            if hasattr(self, "_attr_name"):
                delattr(self, "_attr_name")

        if not description.role:
            if (
                channel_name := get_rpc_channel_name(coordinator.device, key)
            ) is not None:
                self._attr_translation_placeholders = {"channel_name": channel_name}
                if translation_key := description.translation_key or (
                    description.device_class
                    if self._default_to_device_class_name()
                    else None
                ):
                    self._attr_translation_key = f"{translation_key}_with_channel_name"

    @property
    def is_on(self) -> bool:
        """Return true if RPC sensor state is on."""
        return bool(self.attribute_value)


class RpcPresenceBinarySensor(RpcBinarySensor):
    """Represent a RPC binary sensor entity for presence component."""

    @property
    def available(self) -> bool:
        """Available."""
        available = super().available

        return available and self.coordinator.device.config[self.key]["enable"]


class RpcBluTrvBinarySensor(RpcBinarySensor):
    """Represent a RPC BluTrv binary sensor."""

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcBinarySensorDescription,
    ) -> None:
        """Initialize."""

        super().__init__(coordinator, key, attribute, description)
        ble_addr: str = coordinator.device.config[key]["addr"]
        fw_ver = coordinator.device.status[key].get("fw_ver")
        self._attr_device_info = get_blu_trv_device_info(
            coordinator.device.config[key], ble_addr, coordinator.mac, fw_ver
        )


SENSORS: dict[tuple[str, str], BlockBinarySensorDescription] = {
    ("device", "overtemp"): BlockBinarySensorDescription(
        key="device|overtemp",
        translation_key="overheating",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("device", "overpower"): BlockBinarySensorDescription(
        key="device|overpower",
        translation_key="overpowering",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("light", "overpower"): BlockBinarySensorDescription(
        key="light|overpower",
        translation_key="overpowering",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("relay", "overpower"): BlockBinarySensorDescription(
        key="relay|overpower",
        translation_key="overpowering",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("sensor", "dwIsOpened"): BlockBinarySensorDescription(
        key="sensor|dwIsOpened",
        translation_key="door",
        device_class=BinarySensorDeviceClass.OPENING,
        available=lambda block: cast(int, block.dwIsOpened) != -1,
    ),
    ("sensor", "flood"): BlockBinarySensorDescription(
        key="sensor|flood", name="Flood", device_class=BinarySensorDeviceClass.MOISTURE
    ),
    ("sensor", "gas"): BlockBinarySensorDescription(
        key="sensor|gas",
        device_class=BinarySensorDeviceClass.GAS,
        value=lambda value: value in ["mild", "heavy"],
    ),
    ("sensor", "smoke"): BlockBinarySensorDescription(
        key="sensor|smoke", name="Smoke", device_class=BinarySensorDeviceClass.SMOKE
    ),
    ("sensor", "vibration"): BlockBinarySensorDescription(
        key="sensor|vibration",
        device_class=BinarySensorDeviceClass.VIBRATION,
    ),
    ("input", "input"): BlockBinarySensorDescription(
        key="input|input",
        device_class=BinarySensorDeviceClass.POWER,
        removal_condition=is_block_momentary_input,
    ),
    ("relay", "input"): BlockBinarySensorDescription(
        key="relay|input",
        device_class=BinarySensorDeviceClass.POWER,
        removal_condition=is_block_momentary_input,
    ),
    ("device", "input"): BlockBinarySensorDescription(
        key="device|input",
        device_class=BinarySensorDeviceClass.POWER,
        removal_condition=is_block_momentary_input,
    ),
    ("sensor", "extInput"): BlockBinarySensorDescription(
        key="sensor|extInput",
        translation_key="external_input",
        device_class=BinarySensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    ("sensor", "motion"): BlockBinarySensorDescription(
        key="sensor|motion", name="Motion", device_class=BinarySensorDeviceClass.MOTION
    ),
}

REST_SENSORS: Final = {
    "cloud": RestBinarySensorDescription(
        key="cloud",
        translation_key="cloud",
        value=lambda status, _: status["cloud"]["connected"],
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}

RPC_SENSORS: Final = {
    "input": RpcBinarySensorDescription(
        key="input",
        sub_key="state",
        device_class=BinarySensorDeviceClass.POWER,
        removal_condition=is_rpc_momentary_input,
    ),
    "cloud": RpcBinarySensorDescription(
        key="cloud",
        sub_key="connected",
        translation_key="cloud",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "external_power": RpcBinarySensorDescription(
        key="devicepower",
        sub_key="external",
        translation_key="external_power",
        value=lambda status, _: status["present"],
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "overtemp": RpcBinarySensorDescription(
        key="switch",
        sub_key="errors",
        translation_key="overheating",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda status, _: False if status is None else "overtemp" in status,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported=lambda status: status.get("apower") is not None,
    ),
    "overpower": RpcBinarySensorDescription(
        key="switch",
        sub_key="errors",
        translation_key="overpowering",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda status, _: False if status is None else "overpower" in status,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported=lambda status: status.get("apower") is not None,
    ),
    "overvoltage": RpcBinarySensorDescription(
        key="switch",
        sub_key="errors",
        translation_key="overvoltage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda status, _: False if status is None else "overvoltage" in status,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported=lambda status: status.get("apower") is not None,
    ),
    "overcurrent": RpcBinarySensorDescription(
        key="switch",
        sub_key="errors",
        translation_key="overcurrent",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda status, _: False if status is None else "overcurrent" in status,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported=lambda status: status.get("apower") is not None,
    ),
    "smoke": RpcBinarySensorDescription(
        key="smoke",
        sub_key="alarm",
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    "restart": RpcBinarySensorDescription(
        key="sys",
        sub_key="restart_required",
        translation_key="restart_required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "boolean_generic": RpcBinarySensorDescription(
        key="boolean",
        sub_key="value",
        removal_condition=lambda config, _status, key: not is_view_for_platform(
            config, key, BINARY_SENSOR_PLATFORM
        ),
        role="generic",
    ),
    "boolean_has_power": RpcBinarySensorDescription(
        key="boolean",
        sub_key="value",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        role="has_power",
        models={MODEL_FRANKEVER_WATER_VALVE},
    ),
    "calibration": RpcBinarySensorDescription(
        key="blutrv",
        sub_key="errors",
        translation_key="calibration",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda status, _: False if status is None else "not_calibrated" in status,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_class=RpcBluTrvBinarySensor,
    ),
    "flood": RpcBinarySensorDescription(
        key="flood",
        sub_key="alarm",
        translation_key="flood",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    "mute": RpcBinarySensorDescription(
        key="flood",
        sub_key="mute",
        translation_key="mute",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "flood_cable_unplugged": RpcBinarySensorDescription(
        key="flood",
        sub_key="errors",
        value=lambda status, _: False
        if status is None
        else "cable_unplugged" in status,
        translation_key="cable_unplugged",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported=lambda status: status.get("alarm") is not None,
    ),
    "presence_num_objects": RpcBinarySensorDescription(
        key="presence",
        sub_key="num_objects",
        value=lambda status, _: bool(status),
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        entity_class=RpcPresenceBinarySensor,
    ),
    "presencezone_state": RpcBinarySensorDescription(
        key="presencezone",
        sub_key="value",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        entity_class=RpcPresenceBinarySensor,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        if config_entry.data[CONF_SLEEP_PERIOD]:
            async_setup_entry_rpc(
                hass,
                config_entry,
                async_add_entities,
                RPC_SENSORS,
                RpcSleepingBinarySensor,
            )
        else:
            coordinator = config_entry.runtime_data.rpc
            assert coordinator

            async_setup_entry_rpc(
                hass, config_entry, async_add_entities, RPC_SENSORS, RpcBinarySensor
            )

            async_remove_orphaned_entities(
                hass,
                config_entry.entry_id,
                coordinator.mac,
                BINARY_SENSOR_PLATFORM,
                coordinator.device.status,
            )
        return

    if config_entry.data[CONF_SLEEP_PERIOD]:
        async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            SENSORS,
            BlockSleepingBinarySensor,
        )
    else:
        async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            SENSORS,
            BlockBinarySensor,
        )
        async_setup_entry_rest(
            hass,
            config_entry,
            async_add_entities,
            REST_SENSORS,
            RestBinarySensor,
        )


class BlockBinarySensor(ShellyBlockAttributeEntity, BinarySensorEntity):
    """Represent a block binary sensor entity."""

    entity_description: BlockBinarySensorDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block,
        attribute: str,
        description: BlockBinarySensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, block, attribute, description)

        if hasattr(self, "_attr_name"):
            delattr(self, "_attr_name")

        if (
            channel_name := get_block_channel_name(coordinator.device, self.block)
        ) is not None:
            self._attr_translation_placeholders = {"channel_name": channel_name}
            if translation_key := description.translation_key or (
                description.device_class
                if self._default_to_device_class_name()
                else None
            ):
                self._attr_translation_key = f"{translation_key}_with_channel_name"

    @property
    def is_on(self) -> bool:
        """Return true if sensor state is on."""
        return bool(self.attribute_value)


class RestBinarySensor(ShellyRestAttributeEntity, BinarySensorEntity):
    """Represent a REST binary sensor entity."""

    entity_description: RestBinarySensorDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        attribute: str,
        description: RestBinarySensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, attribute, description)

        if hasattr(self, "_attr_name"):
            delattr(self, "_attr_name")

        if (
            channel_name := get_block_channel_name(coordinator.device, None)
        ) is not None:
            self._attr_translation_placeholders = {"channel_name": channel_name}
            if translation_key := description.translation_key or (
                description.device_class
                if self._default_to_device_class_name()
                else None
            ):
                self._attr_translation_key = f"{translation_key}_with_channel_name"

    @property
    def is_on(self) -> bool:
        """Return true if REST sensor state is on."""
        return bool(self.attribute_value)


class BlockSleepingBinarySensor(
    ShellySleepingBlockAttributeEntity, BinarySensorEntity, RestoreEntity
):
    """Represent a block sleeping binary sensor."""

    entity_description: BlockBinarySensorDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block | None,
        attribute: str,
        description: BlockBinarySensorDescription,
        entry: RegistryEntry | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        super().__init__(coordinator, block, attribute, description, entry)

        if block is not None:
            if hasattr(self, "_attr_name"):
                delattr(self, "_attr_name")
            if (
                channel_name := get_block_channel_name(coordinator.device, block)
            ) is not None:
                self._attr_translation_placeholders = {"channel_name": channel_name}
                if translation_key := description.translation_key or (
                    description.device_class
                    if self._default_to_device_class_name()
                    else None
                ):
                    self._attr_translation_key = f"{translation_key}_with_channel_name"

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.last_state = await self.async_get_last_state()

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor state is on."""
        if self.block is not None:
            return bool(self.attribute_value)

        if self.last_state is None:
            return None

        return self.last_state.state == STATE_ON


class RpcSleepingBinarySensor(
    ShellySleepingRpcAttributeEntity, BinarySensorEntity, RestoreEntity
):
    """Represent a RPC sleeping binary sensor entity."""

    entity_description: RpcBinarySensorDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcBinarySensorDescription,
        entry: RegistryEntry | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        super().__init__(coordinator, key, attribute, description, entry)

        if coordinator.device.initialized:
            if description.role != "generic":
                if hasattr(self, "_attr_name"):
                    delattr(self, "_attr_name")
            if not description.role:
                if (
                    channel_name := get_rpc_channel_name(coordinator.device, key)
                ) is not None:
                    self._attr_translation_placeholders = {"channel_name": channel_name}
                    if translation_key := description.translation_key or (
                        description.device_class
                        if self._default_to_device_class_name()
                        else None
                    ):
                        self._attr_translation_key = (
                            f"{translation_key}_with_channel_name"
                        )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.last_state = await self.async_get_last_state()

    @property
    def is_on(self) -> bool | None:
        """Return true if RPC sensor state is on."""
        if self.coordinator.device.initialized:
            return bool(self.attribute_value)

        if self.last_state is None:
            return None

        return self.last_state.state == STATE_ON
