"""Switch for Shelly."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast, override

from aioshelly.block_device import Block
from aioshelly.const import RPC_GENERATIONS
from aioshelly.exceptions import RpcCallError
from aioshelly.rpc_device import RpcDevice

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    MODEL_FRANKEVER_IRRIGATION_CONTROLLER,
    MODEL_LINKEDGO_ST802_THERMOSTAT,
    MODEL_LINKEDGO_ST1820_THERMOSTAT,
    MODEL_NEO_WATER_VALVE,
    ROLE_GENERIC,
    RPC_ERROR_CODE_REMOTE_DISABLED,
)
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    BlockEntityDescription,
    RpcEntityDescription,
    ShellyBlockAttributeEntity,
    ShellyRpcAttributeEntity,
    ShellyRpcEntity,
    ShellySleepingBlockAttributeEntity,
    async_setup_entry_block,
    async_setup_entry_rpc,
    rpc_call,
)
from .utils import (
    async_remove_orphaned_entities,
    get_device_entry_gen,
    get_rpc_channel_name,
    get_virtual_component_ids,
    is_block_exclude_from_relay,
    is_rpc_exclude_from_relay,
    is_rpc_ledstrip_control_available,
    is_rpc_wall_display_brightness_supported,
    is_view_for_platform,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BlockSwitchDescription(BlockEntityDescription, SwitchEntityDescription):
    """Class to describe a BLOCK switch."""


BLOCK_RELAY_SWITCHES = {
    ("relay", "output"): BlockSwitchDescription(
        key="relay|output",
        removal_condition=is_block_exclude_from_relay,
    )
}

BLOCK_SLEEPING_MOTION_SWITCH = {
    ("sensor", "motionActive"): BlockSwitchDescription(
        key="sensor|motionActive",
        translation_key="motion_detection",
        entity_category=EntityCategory.CONFIG,
    )
}


@dataclass(frozen=True, kw_only=True)
class RpcSwitchDescription(RpcEntityDescription, SwitchEntityDescription):
    """Class to describe a RPC virtual switch."""

    is_on: Callable[[dict[str, Any]], bool]
    method: Callable[[RpcDevice, int, bool], Awaitable[Any]]


class RpcSwitch(ShellyRpcAttributeEntity, SwitchEntity):
    """Entity that controls a switch on RPC based Shelly devices."""

    entity_description: RpcSwitchDescription
    _id: int

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcSwitchDescription,
    ) -> None:
        """Initialize switch."""
        super().__init__(coordinator, key, attribute, description)

        if description.translation_key is None and description.key in (
            "cb",
            "switch",
            "script",
        ):
            self._attr_name = get_rpc_channel_name(coordinator.device, key)

    @property
    @override
    def is_on(self) -> bool:
        """If switch is on."""
        return self.entity_description.is_on(self.status)

    @rpc_call
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self.entity_description.method(self.coordinator.device, self._id, True)

    @rpc_call
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self.entity_description.method(self.coordinator.device, self._id, False)


class RpcConfigSwitch(RpcSwitch):
    """Represent a RPC switch entity for a device config value."""

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcSwitchDescription,
    ) -> None:
        """Initialize switch."""
        super().__init__(coordinator, key, attribute, description)
        self.configure_translation_attributes()

    @property
    @override
    def is_on(self) -> bool:
        """If switch is on."""
        return self.entity_description.is_on(self.coordinator.device.config[self.key])


class RpcCircuitBreakerSwitch(RpcSwitch):
    """Entity that controls a circuit breaker on RPC based Shelly devices."""

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and not self.status["safety"]

    @rpc_call
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on circuit breaker."""
        try:
            await self.entity_description.method(
                self.coordinator.device, self._id, True
            )
        except RpcCallError as err:
            if err.code == RPC_ERROR_CODE_REMOTE_DISABLED:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="circuit_breaker_remote_disabled",
                    translation_placeholders={
                        "entity": self.entity_id,
                        "device": self.coordinator.name,
                    },
                ) from err
            raise


class RpcRelaySwitch(RpcSwitch):
    """Entity that controls a switch on RPC based Shelly devices."""

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcSwitchDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, key, attribute, description)
        self._attr_unique_id: str = f"{coordinator.mac}-{key}"


class RpcFanBoostSwitch(RpcSwitch):
    """Entity that controls the fan boost on RPC based Shelly devices."""

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        # The device rejects boost in manual mode
        return super().available and self.status["mode"] == "auto"


class RpcLedStripSwitch(RpcSwitch):
    """Entity that controls a LED strip effect option on RPC based Shelly devices."""

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        if TYPE_CHECKING:
            assert self.entity_description.sub_key is not None

        return super().available and is_rpc_ledstrip_control_available(
            self.coordinator.config_entry.runtime_data.rpc_ledstrip_effects,
            self.status,
            self.entity_description.sub_key,
        )


class RpcWallDisplayAutoBrightnessSwitch(ShellyRpcEntity, SwitchEntity):
    """Represent a RPC Wall Display auto brightness switch."""

    def __init__(
        self, coordinator: ShellyRpcCoordinator, description: SwitchEntityDescription
    ) -> None:
        """Initialize Wall Display auto brightness switch."""
        super().__init__(coordinator, "ui")
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.mac}-ui-{description.key}"

    @property
    @override
    def is_on(self) -> bool:
        """Return true if auto brightness is on."""
        return cast(bool, self.coordinator.device.config["ui"]["brightness"]["auto"])

    @rpc_call
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on auto brightness."""
        await self.coordinator.device.wall_display_ui_setconfig(
            {"brightness": {"auto": True}}
        )

    @rpc_call
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off auto brightness."""
        await self.coordinator.device.wall_display_ui_setconfig(
            {"brightness": {"auto": False}}
        )


WALL_DISPLAY_AUTO_BRIGHTNESS_SWITCH = SwitchEntityDescription(
    key="auto",
    translation_key="auto_brightness",
    entity_category=EntityCategory.CONFIG,
)


RPC_SWITCHES = (
    RpcSwitchDescription(
        key="switch",
        components=("switch",),
        sub_key="output",
        removal_condition=is_rpc_exclude_from_relay,
        is_on=lambda status: bool(status["output"]),
        method=lambda device, id_, value: device.switch_set(id_, value),
        entity_class=RpcRelaySwitch,
    ),
    RpcSwitchDescription(
        key="cb",
        components=("cb",),
        sub_key="output",
        is_on=lambda status: bool(status["output"]),
        method=lambda device, id_, value: device.cb_set(id_, value),
        entity_class=RpcCircuitBreakerSwitch,
    ),
    RpcSwitchDescription(
        key="boolean_generic",
        components=("boolean",),
        sub_key="value",
        removal_condition=lambda config, _, key: (
            not is_view_for_platform(config, key, SWITCH_DOMAIN)
        ),
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role=ROLE_GENERIC,
    ),
    RpcSwitchDescription(
        key="boolean_anti_freeze",
        components=("boolean",),
        sub_key="value",
        translation_key="frost_protection",
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role="anti_freeze",
        models={MODEL_LINKEDGO_ST802_THERMOSTAT, MODEL_LINKEDGO_ST1820_THERMOSTAT},
    ),
    RpcSwitchDescription(
        key="boolean_child_lock",
        components=("boolean",),
        sub_key="value",
        translation_key="child_lock",
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role="child_lock",
        models={MODEL_LINKEDGO_ST1820_THERMOSTAT},
    ),
    RpcSwitchDescription(
        key="boolean_enable",
        components=("boolean",),
        sub_key="value",
        translation_key="thermostat_enabled",
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role="enable",
        models={MODEL_LINKEDGO_ST802_THERMOSTAT, MODEL_LINKEDGO_ST1820_THERMOSTAT},
    ),
    RpcSwitchDescription(
        key="boolean_start_charging",
        components=("boolean",),
        sub_key="value",
        translation_key="charging",
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role="start_charging",
    ),
    RpcSwitchDescription(
        key="boolean_state",
        components=("boolean",),
        sub_key="value",
        translation_key="valve_opened",
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role="state",
        models={MODEL_NEO_WATER_VALVE},
    ),
    RpcSwitchDescription(
        key="boolean_zone0",
        components=("boolean",),
        sub_key="value",
        translation_key="zone_with_number",
        translation_placeholders={"zone_number": "1"},
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role="zone0",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    RpcSwitchDescription(
        key="boolean_zone1",
        components=("boolean",),
        sub_key="value",
        translation_key="zone_with_number",
        translation_placeholders={"zone_number": "2"},
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role="zone1",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    RpcSwitchDescription(
        key="boolean_zone2",
        components=("boolean",),
        sub_key="value",
        translation_key="zone_with_number",
        translation_placeholders={"zone_number": "3"},
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role="zone2",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    RpcSwitchDescription(
        key="boolean_zone3",
        components=("boolean",),
        sub_key="value",
        translation_key="zone_with_number",
        translation_placeholders={"zone_number": "4"},
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role="zone3",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    RpcSwitchDescription(
        key="boolean_zone4",
        components=("boolean",),
        sub_key="value",
        translation_key="zone_with_number",
        translation_placeholders={"zone_number": "5"},
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role="zone4",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    RpcSwitchDescription(
        key="boolean_zone5",
        components=("boolean",),
        sub_key="value",
        translation_key="zone_with_number",
        translation_placeholders={"zone_number": "6"},
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method=lambda device, id_, value: device.boolean_set(id_, value),
        role="zone5",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    RpcSwitchDescription(
        key="script",
        components=("script",),
        sub_key="running",
        is_on=lambda status: bool(status["running"]),
        method=lambda device, id_, value: (
            device.script_start(id_) if value else device.script_stop(id_)
        ),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    RpcSwitchDescription(
        key="cury_left",
        components=("cury",),
        sub_key="slots",
        translation_key="left_slot",
        is_on=lambda status: bool(status["slots"]["left"]["on"]),
        method=lambda device, id_, value: device.cury_set(id_, "left", value),
        available=lambda status: (
            (left := status["left"]) is not None
            and left.get("vial", {}).get("level", -1) != -1
        ),
    ),
    RpcSwitchDescription(
        key="cury_left_boost",
        components=("cury",),
        sub_key="slots",
        translation_key="left_slot_boost",
        is_on=lambda status: status["slots"]["left"]["boost"] is not None,
        method=lambda device, id_, value: (
            device.cury_boost(id_, "left")
            if value
            else device.cury_stop_boost(id_, "left")
        ),
        available=lambda status: (
            (left := status["left"]) is not None
            and left.get("vial", {}).get("level", -1) != -1
        ),
    ),
    RpcSwitchDescription(
        key="cury_right",
        components=("cury",),
        sub_key="slots",
        translation_key="right_slot",
        is_on=lambda status: bool(status["slots"]["right"]["on"]),
        method=lambda device, id_, value: device.cury_set(id_, "right", value),
        available=lambda status: (
            (right := status["right"]) is not None
            and right.get("vial", {}).get("level", -1) != -1
        ),
    ),
    RpcSwitchDescription(
        key="cury_right_boost",
        components=("cury",),
        sub_key="slots",
        translation_key="right_slot_boost",
        is_on=lambda status: status["slots"]["right"]["boost"] is not None,
        method=lambda device, id_, value: (
            device.cury_boost(id_, "right")
            if value
            else device.cury_stop_boost(id_, "right")
        ),
        available=lambda status: (
            (right := status["right"]) is not None
            and right.get("vial", {}).get("level", -1) != -1
        ),
    ),
    RpcSwitchDescription(
        key="cury_away_mode",
        components=("cury",),
        sub_key="away_mode",
        translation_key="cury_away_mode",
        is_on=lambda status: status["away_mode"],
        method=lambda device, id_, value: device.cury_set_away_mode(id_, value),
    ),
    RpcSwitchDescription(
        key="fan_boost",
        components=("fan",),
        sub_key="boost",
        translation_key="boost",
        is_on=lambda status: status["boost"]["active"],
        method=lambda device, id_, value: (
            device.fan_boost(id_) if value else device.fan_stop_boost(id_)
        ),
        entity_class=RpcFanBoostSwitch,
    ),
    RpcSwitchDescription(
        key="ledstrip_reverse",
        components=("ledstrip",),
        sub_key="reverse",
        translation_key="effect_reverse",
        is_on=lambda status: bool(status["reverse"]),
        method=lambda device, id_, value: device.ledstrip_set(id_, {"reverse": value}),
        supported=lambda _: True,
        entity_class=RpcLedStripSwitch,
    ),
    RpcSwitchDescription(
        key="switch_in_locked",
        components=("switch",),
        translation_key="input_lock",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        removal_condition=lambda config, _status, key: "in_locked" not in config[key],
        is_on=lambda config: bool(config["in_locked"]),
        method=lambda device, id_, value: device.switch_setconfig(
            id_, {"in_locked": value}
        ),
        entity_class=RpcConfigSwitch,
    ),
    RpcSwitchDescription(
        key="cover_in_locked",
        components=("cover",),
        translation_key="input_lock",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        removal_condition=lambda config, _status, key: "in_locked" not in config[key],
        is_on=lambda config: bool(config["in_locked"]),
        method=lambda device, id_, value: device.cover_setconfig(
            id_, {"in_locked": value}
        ),
        entity_class=RpcConfigSwitch,
    ),
    RpcSwitchDescription(
        key="camera_privacy",
        components=("camera",),
        sub_key="privacy",
        translation_key="camera_privacy",
        is_on=lambda status: status["privacy"],
        method=lambda device, id_, value: device.set_camera_privacy(id_, value),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        return _async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return _async_setup_block_entry(hass, config_entry, async_add_entities)


@callback
def _async_setup_block_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for BLOCK device."""
    coordinator = config_entry.runtime_data.block
    assert coordinator

    async_setup_entry_block(
        hass, config_entry, async_add_entities, BLOCK_RELAY_SWITCHES, BlockRelaySwitch
    )

    async_setup_entry_block(
        hass,
        config_entry,
        async_add_entities,
        BLOCK_SLEEPING_MOTION_SWITCH,
        BlockSleepingMotionSwitch,
    )


@callback
def _async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    coordinator = config_entry.runtime_data.rpc
    assert coordinator

    async_setup_entry_rpc(
        hass, config_entry, async_add_entities, RPC_SWITCHES, RpcSwitch
    )

    # The Wall Display does not report the ui component in the status
    if is_rpc_wall_display_brightness_supported(coordinator):
        async_add_entities(
            [
                RpcWallDisplayAutoBrightnessSwitch(
                    coordinator, WALL_DISPLAY_AUTO_BRIGHTNESS_SWITCH
                )
            ]
        )

    # the user can remove virtual components from the device configuration, so we need
    # to remove orphaned entities
    virtual_switch_ids = get_virtual_component_ids(
        coordinator.device.config, SWITCH_DOMAIN
    )
    async_remove_orphaned_entities(
        hass,
        config_entry.entry_id,
        coordinator.mac,
        SWITCH_DOMAIN,
        virtual_switch_ids,
        "boolean",
    )

    # if the script is removed, from the device configuration, we need
    # to remove orphaned entities
    async_remove_orphaned_entities(
        hass,
        config_entry.entry_id,
        coordinator.mac,
        SWITCH_DOMAIN,
        coordinator.device.status,
        "script",
    )

    # if the climate is removed, from the device configuration, we need
    # to remove orphaned entities
    async_remove_orphaned_entities(
        hass,
        config_entry.entry_id,
        coordinator.mac,
        CLIMATE_DOMAIN,
        coordinator.device.status,
        "thermostat",
    )


class BlockSleepingMotionSwitch(
    ShellySleepingBlockAttributeEntity, RestoreEntity, SwitchEntity
):
    """Entity that controls Motion Sensor on Block based Shelly devices."""

    entity_description: BlockSwitchDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block | None,
        attribute: str,
        description: BlockSwitchDescription,
        entry: RegistryEntry | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        super().__init__(coordinator, block, attribute, description, entry)
        self.last_state: State | None = None

    @property
    @override
    def is_on(self) -> bool | None:
        """If motion is active."""
        if self.block is not None:
            return bool(self.block.motionActive)

        if self.last_state is None:
            return None

        return self.last_state.state == STATE_ON

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate switch."""
        await self.coordinator.device.set_shelly_motion_detection(True)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate switch."""
        await self.coordinator.device.set_shelly_motion_detection(False)
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self.last_state = last_state


class BlockRelaySwitch(ShellyBlockAttributeEntity, SwitchEntity):
    """Entity that controls a relay on Block based Shelly devices."""

    entity_description: BlockSwitchDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block,
        attribute: str,
        description: BlockSwitchDescription,
    ) -> None:
        """Initialize relay switch."""
        super().__init__(coordinator, block, attribute, description)
        self.control_result: dict[str, Any] | None = None
        self._attr_name = None  # Main device entity
        self._attr_unique_id: str = f"{coordinator.mac}-{block.description}"

    @property
    @override
    def is_on(self) -> bool:
        """If switch is on."""
        if self.control_result:
            return cast(bool, self.control_result["ison"])

        return bool(self.block.output)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        self.control_result = await self.set_state(turn="on")
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        self.control_result = await self.set_state(turn="off")
        self.async_write_ha_state()

    @callback
    @override
    def _update_callback(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()
