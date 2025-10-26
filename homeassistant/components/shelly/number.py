"""Number for Shelly."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, cast

from aioshelly.block_device import Block
from aioshelly.const import RPC_GENERATIONS
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError

from homeassistant.components.number import (
    DOMAIN as NUMBER_PLATFORM,
    NumberEntity,
    NumberEntityDescription,
    NumberExtraStoredData,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry

from .const import (
    CONF_SLEEP_PERIOD,
    DOMAIN,
    LOGGER,
    MODEL_FRANKEVER_WATER_VALVE,
    MODEL_LINKEDGO_ST802_THERMOSTAT,
    MODEL_LINKEDGO_ST1820_THERMOSTAT,
    MODEL_TOP_EV_CHARGER_EVE01,
    ROLE_GENERIC,
    VIRTUAL_NUMBER_MODE_MAP,
)
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    BlockEntityDescription,
    RpcEntityDescription,
    ShellyRpcAttributeEntity,
    ShellySleepingBlockAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rpc,
    rpc_call,
)
from .utils import (
    async_remove_orphaned_entities,
    get_blu_trv_device_info,
    get_device_entry_gen,
    get_virtual_component_ids,
    get_virtual_component_unit,
    is_view_for_platform,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BlockNumberDescription(BlockEntityDescription, NumberEntityDescription):
    """Class to describe a BLOCK sensor."""

    rest_path: str = ""
    rest_arg: str = ""


@dataclass(frozen=True, kw_only=True)
class RpcNumberDescription(RpcEntityDescription, NumberEntityDescription):
    """Class to describe a RPC number entity."""

    max_fn: Callable[[dict], float] | None = None
    min_fn: Callable[[dict], float] | None = None
    step_fn: Callable[[dict], float] | None = None
    mode_fn: Callable[[dict], NumberMode] | None = None
    slot: str | None = None
    method: str


class RpcNumber(ShellyRpcAttributeEntity, NumberEntity):
    """Represent a RPC number entity."""

    entity_description: RpcNumberDescription
    attribute_value: float | None
    _id: int | None

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcNumberDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, key, attribute, description)

        if description.max_fn is not None:
            self._attr_native_max_value = description.max_fn(
                coordinator.device.config[key]
            )
        if description.min_fn is not None:
            self._attr_native_min_value = description.min_fn(
                coordinator.device.config[key]
            )
        if description.step_fn is not None:
            self._attr_native_step = description.step_fn(coordinator.device.config[key])
        if description.mode_fn is not None:
            self._attr_mode = description.mode_fn(coordinator.device.config[key])

    @property
    def native_value(self) -> float | None:
        """Return value of number."""
        return self.attribute_value

    @rpc_call
    async def async_set_native_value(self, value: float) -> None:
        """Change the value."""
        method = getattr(self.coordinator.device, self.entity_description.method)

        if TYPE_CHECKING:
            assert method is not None

        await method(self._id, value)


class RpcCuryIntensityNumber(RpcNumber):
    """Represent a RPC Cury Intensity entity."""

    @rpc_call
    async def async_set_native_value(self, value: float) -> None:
        """Change the value."""
        method = getattr(self.coordinator.device, self.entity_description.method)

        if TYPE_CHECKING:
            assert method is not None

        await method(
            self._id, slot=self.entity_description.slot, intensity=round(value)
        )


class RpcBluTrvNumber(RpcNumber):
    """Represent a RPC BluTrv number."""

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcNumberDescription,
    ) -> None:
        """Initialize."""

        super().__init__(coordinator, key, attribute, description)
        ble_addr: str = coordinator.device.config[key]["addr"]
        fw_ver = coordinator.device.status[key].get("fw_ver")
        self._attr_device_info = get_blu_trv_device_info(
            coordinator.device.config[key], ble_addr, coordinator.mac, fw_ver
        )


class RpcBluTrvExtTempNumber(RpcBluTrvNumber):
    """Represent a RPC BluTrv External Temperature number."""

    _reported_value: float | None = None

    @property
    def native_value(self) -> float | None:
        """Return value of number."""
        return self._reported_value

    async def async_set_native_value(self, value: float) -> None:
        """Change the value."""
        await super().async_set_native_value(value)

        self._reported_value = value
        self.async_write_ha_state()


NUMBERS: dict[tuple[str, str], BlockNumberDescription] = {
    ("device", "valvePos"): BlockNumberDescription(
        key="device|valvepos",
        translation_key="valve_position",
        name="Valve position",
        native_unit_of_measurement=PERCENTAGE,
        available=lambda block: cast(int, block.valveError) != 1,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        rest_path="thermostat/0",
        rest_arg="pos",
    ),
}


RPC_NUMBERS: Final = {
    "external_temperature": RpcNumberDescription(
        key="blutrv",
        sub_key="current_C",
        translation_key="external_temperature",
        name="External temperature",
        native_min_value=-50,
        native_max_value=50,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        method="blu_trv_set_external_temperature",
        entity_class=RpcBluTrvExtTempNumber,
    ),
    "number_generic": RpcNumberDescription(
        key="number",
        sub_key="value",
        removal_condition=lambda config, _status, key: not is_view_for_platform(
            config, key, NUMBER_PLATFORM
        ),
        max_fn=lambda config: config["max"],
        min_fn=lambda config: config["min"],
        mode_fn=lambda config: VIRTUAL_NUMBER_MODE_MAP.get(
            config["meta"]["ui"]["view"], NumberMode.BOX
        ),
        step_fn=lambda config: config["meta"]["ui"].get("step"),
        unit=get_virtual_component_unit,
        method="number_set",
        role=ROLE_GENERIC,
    ),
    "number_current_limit": RpcNumberDescription(
        key="number",
        sub_key="value",
        max_fn=lambda config: config["max"],
        min_fn=lambda config: config["min"],
        mode_fn=lambda config: NumberMode.SLIDER,
        step_fn=lambda config: config["meta"]["ui"].get("step"),
        unit=get_virtual_component_unit,
        method="number_set",
        role="current_limit",
        models={MODEL_TOP_EV_CHARGER_EVE01},
    ),
    "number_position": RpcNumberDescription(
        key="number",
        sub_key="value",
        entity_registry_enabled_default=False,
        max_fn=lambda config: config["max"],
        min_fn=lambda config: config["min"],
        mode_fn=lambda config: NumberMode.SLIDER,
        step_fn=lambda config: config["meta"]["ui"].get("step"),
        unit=get_virtual_component_unit,
        method="number_set",
        role="position",
        models={MODEL_FRANKEVER_WATER_VALVE},
    ),
    "number_target_humidity": RpcNumberDescription(
        key="number",
        sub_key="value",
        entity_registry_enabled_default=False,
        max_fn=lambda config: config["max"],
        min_fn=lambda config: config["min"],
        mode_fn=lambda config: NumberMode.SLIDER,
        step_fn=lambda config: config["meta"]["ui"].get("step"),
        unit=get_virtual_component_unit,
        method="number_set",
        role="target_humidity",
        models={MODEL_LINKEDGO_ST802_THERMOSTAT, MODEL_LINKEDGO_ST1820_THERMOSTAT},
    ),
    "number_target_temperature": RpcNumberDescription(
        key="number",
        sub_key="value",
        entity_registry_enabled_default=False,
        max_fn=lambda config: config["max"],
        min_fn=lambda config: config["min"],
        mode_fn=lambda config: NumberMode.SLIDER,
        step_fn=lambda config: config["meta"]["ui"].get("step"),
        unit=get_virtual_component_unit,
        method="number_set",
        role="target_temperature",
        models={MODEL_LINKEDGO_ST802_THERMOSTAT, MODEL_LINKEDGO_ST1820_THERMOSTAT},
    ),
    "valve_position": RpcNumberDescription(
        key="blutrv",
        sub_key="pos",
        translation_key="valve_position",
        name="Valve position",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=PERCENTAGE,
        method="blu_trv_set_valve_position",
        removal_condition=lambda config, _status, key: config[key].get("enable", True)
        is True,
        entity_class=RpcBluTrvNumber,
    ),
    "left_slot_intensity": RpcNumberDescription(
        key="cury",
        sub_key="slots",
        name="Left slot intensity",
        value=lambda status, _: status["left"]["intensity"],
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=PERCENTAGE,
        method="cury_set",
        slot="left",
        available=lambda status: (left := status["left"]) is not None
        and left.get("vial", {}).get("level", -1) != -1,
        entity_class=RpcCuryIntensityNumber,
    ),
    "right_slot_intensity": RpcNumberDescription(
        key="cury",
        sub_key="slots",
        name="Right slot intensity",
        value=lambda status, _: status["right"]["intensity"],
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=PERCENTAGE,
        method="cury_set",
        slot="right",
        available=lambda status: (right := status["right"]) is not None
        and right.get("vial", {}).get("level", -1) != -1,
        entity_class=RpcCuryIntensityNumber,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
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
    if config_entry.data[CONF_SLEEP_PERIOD]:
        async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            NUMBERS,
            BlockSleepingNumber,
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
        hass, config_entry, async_add_entities, RPC_NUMBERS, RpcNumber
    )

    # the user can remove virtual components from the device configuration, so
    # we need to remove orphaned entities
    virtual_number_ids = get_virtual_component_ids(
        coordinator.device.config, NUMBER_PLATFORM
    )
    async_remove_orphaned_entities(
        hass,
        config_entry.entry_id,
        coordinator.mac,
        NUMBER_PLATFORM,
        virtual_number_ids,
        "number",
    )


class BlockSleepingNumber(ShellySleepingBlockAttributeEntity, RestoreNumber):
    """Represent a block sleeping number."""

    entity_description: BlockNumberDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block | None,
        attribute: str,
        description: BlockNumberDescription,
        entry: RegistryEntry | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        self.restored_data: NumberExtraStoredData | None = None
        super().__init__(coordinator, block, attribute, description, entry)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.restored_data = await self.async_get_last_number_data()

    @property
    def native_value(self) -> float | None:
        """Return value of number."""
        if self.block is not None:
            return cast(float, self.attribute_value)

        if self.restored_data is None:
            return None

        return cast(float, self.restored_data.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set value."""
        # Example for Shelly Valve: http://192.168.188.187/thermostat/0?pos=13.0
        await self._set_state_full_path(
            self.entity_description.rest_path,
            {self.entity_description.rest_arg: value},
        )
        self.async_write_ha_state()

    async def _set_state_full_path(self, path: str, params: Any) -> Any:
        """Set block state (HTTP request)."""
        LOGGER.debug("Setting state for entity %s, state: %s", self.name, params)
        try:
            return await self.coordinator.device.http_request("get", path, params)
        except DeviceConnectionError as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_communication_action_error",
                translation_placeholders={
                    "entity": self.entity_id,
                    "device": self.coordinator.name,
                },
            ) from err
        except InvalidAuthError:
            await self.coordinator.async_shutdown_device_and_start_reauth()
