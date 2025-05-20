"""Climate support for Shelly."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, cast

from aioshelly.block_device import Block
from aioshelly.const import BLU_TRV_IDENTIFIER, BLU_TRV_MODEL_NAME, RPC_GENERATIONS
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_conversion import TemperatureConverter
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import (
    BLU_TRV_TEMPERATURE_SETTINGS,
    DOMAIN,
    LOGGER,
    NOT_CALIBRATED_ISSUE_ID,
    RPC_THERMOSTAT_SETTINGS,
    SHTRV_01_TEMPERATURE_SETTINGS,
)
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .entity import ShellyRpcEntity, rpc_call
from .utils import (
    async_remove_shelly_entity,
    get_device_entry_gen,
    get_rpc_key_ids,
    is_rpc_thermostat_internal_actuator,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate device."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        async_setup_rpc_entry(hass, config_entry, async_add_entities)
        return

    coordinator = config_entry.runtime_data.block
    assert coordinator
    if coordinator.device.initialized:
        async_setup_climate_entities(async_add_entities, coordinator)
    else:
        async_restore_climate_entities(
            hass, config_entry, async_add_entities, coordinator
        )


@callback
def async_setup_climate_entities(
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: ShellyBlockCoordinator,
) -> None:
    """Set up online climate devices."""

    device_block: Block | None = None
    sensor_block: Block | None = None

    assert coordinator.device.blocks

    for block in coordinator.device.blocks:
        if block.type == "device":
            device_block = block
        if hasattr(block, "targetTemp"):
            sensor_block = block

    if sensor_block and device_block:
        LOGGER.debug("Setup online climate device %s", coordinator.name)
        async_add_entities(
            [BlockSleepingClimate(coordinator, sensor_block, device_block)]
        )


@callback
def async_restore_climate_entities(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: ShellyBlockCoordinator,
) -> None:
    """Restore sleeping climate devices."""

    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)

    for entry in entries:
        if entry.domain != CLIMATE_DOMAIN:
            continue

        LOGGER.debug("Setup sleeping climate device %s", coordinator.name)
        LOGGER.debug("Found entry %s [%s]", entry.original_name, entry.domain)
        async_add_entities([BlockSleepingClimate(coordinator, None, None, entry)])
        break


@callback
def async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    coordinator = config_entry.runtime_data.rpc
    assert coordinator
    climate_key_ids = get_rpc_key_ids(coordinator.device.status, "thermostat")
    blutrv_key_ids = get_rpc_key_ids(coordinator.device.status, BLU_TRV_IDENTIFIER)

    climate_ids = []
    for id_ in climate_key_ids:
        climate_ids.append(id_)
        # There are three configuration scenarios for WallDisplay:
        # - relay mode (no thermostat)
        # - thermostat mode using the internal relay as an actuator
        # - thermostat mode using an external (from another device) relay as
        #   an actuator
        if is_rpc_thermostat_internal_actuator(coordinator.device.status):
            # Wall Display relay is used as the thermostat actuator,
            # we need to remove a switch entity
            unique_id = f"{coordinator.mac}-switch:{id_}"
            async_remove_shelly_entity(hass, "switch", unique_id)

    if climate_ids:
        async_add_entities(RpcClimate(coordinator, id_) for id_ in climate_ids)

    if blutrv_key_ids:
        async_add_entities(RpcBluTrvClimate(coordinator, id_) for id_ in blutrv_key_ids)


@dataclass
class ShellyClimateExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    last_target_temp: float | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the text data."""
        return asdict(self)


class BlockSleepingClimate(
    CoordinatorEntity[ShellyBlockCoordinator], RestoreEntity, ClimateEntity
):
    """Representation of a Shelly climate device."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_max_temp = SHTRV_01_TEMPERATURE_SETTINGS["max"]
    _attr_min_temp = SHTRV_01_TEMPERATURE_SETTINGS["min"]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = SHTRV_01_TEMPERATURE_SETTINGS["step"]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        sensor_block: Block | None,
        device_block: Block | None,
        entry: RegistryEntry | None = None,
    ) -> None:
        """Initialize climate."""
        super().__init__(coordinator)

        self.block: Block | None = sensor_block
        self.control_result: dict[str, Any] | None = None
        self.device_block: Block | None = device_block
        self.last_state: State | None = None
        self.last_state_attributes: Mapping[str, Any]
        self._preset_modes: list[str] = []
        self._last_target_temp = SHTRV_01_TEMPERATURE_SETTINGS["default"]
        self._attr_name = coordinator.name

        if self.block is not None and self.device_block is not None:
            self._unique_id = f"{self.coordinator.mac}-{self.block.description}"
            assert self.block.channel
            self._preset_modes = [
                PRESET_NONE,
                *coordinator.device.settings["thermostats"][int(self.block.channel)][
                    "schedule_profile_names"
                ],
            ]
        elif entry is not None:
            self._unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, coordinator.mac)},
        )

        self._channel = cast(int, self._unique_id.split("_")[1])

    @property
    def extra_restore_state_data(self) -> ShellyClimateExtraStoredData:
        """Return text specific state data to be restored."""
        return ShellyClimateExtraStoredData(self._last_target_temp)

    @property
    def unique_id(self) -> str:
        """Set unique id of entity."""
        return self._unique_id

    @property
    def target_temperature(self) -> float | None:
        """Set target temperature."""
        if self.block is not None:
            return cast(float, self.block.targetTemp)
        # The restored value can be in Fahrenheit so we have to convert it to Celsius
        # because we use this unit internally in integration.
        target_temp = self.last_state_attributes.get("temperature")
        if self.hass.config.units is US_CUSTOMARY_SYSTEM and target_temp:
            return TemperatureConverter.convert(
                cast(float, target_temp),
                UnitOfTemperature.FAHRENHEIT,
                UnitOfTemperature.CELSIUS,
            )
        return target_temp

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        if self.block is not None:
            return cast(float, self.block.temp)
        # The restored value can be in Fahrenheit so we have to convert it to Celsius
        # because we use this unit internally in integration.
        current_temp = self.last_state_attributes.get("current_temperature")
        if self.hass.config.units is US_CUSTOMARY_SYSTEM and current_temp:
            return TemperatureConverter.convert(
                cast(float, current_temp),
                UnitOfTemperature.FAHRENHEIT,
                UnitOfTemperature.CELSIUS,
            )
        return current_temp

    @property
    def available(self) -> bool:
        """Device availability."""
        if self.device_block is not None:
            return not cast(bool, self.device_block.valveError)
        return super().available

    @property
    def hvac_mode(self) -> HVACMode:
        """HVAC current mode."""
        if self.device_block is None:
            if self.last_state and self.last_state.state in list(HVACMode):
                return HVACMode(self.last_state.state)
            return HVACMode.OFF

        if self.device_block.mode is None or self._check_is_off():
            return HVACMode.OFF

        return HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        """Preset current mode."""
        if self.device_block is None:
            return self.last_state_attributes.get("preset_mode")
        if self.device_block.mode is None:
            return PRESET_NONE
        return self._preset_modes[cast(int, self.device_block.mode)]

    @property
    def hvac_action(self) -> HVACAction:
        """HVAC current action."""
        if (
            self.device_block is None
            or self.device_block.status is None
            or self._check_is_off()
        ):
            return HVACAction.OFF

        return HVACAction.HEATING if bool(self.device_block.status) else HVACAction.IDLE

    @property
    def preset_modes(self) -> list[str]:
        """Preset available modes."""
        return self._preset_modes

    def _check_is_off(self) -> bool:
        """Return if valve is off or on."""
        return bool(
            self.target_temperature is None
            or (self.target_temperature <= self._attr_min_temp)
        )

    async def set_state_full_path(self, **kwargs: Any) -> Any:
        """Set block state (HTTP request)."""
        LOGGER.debug("Setting state for entity %s, state: %s", self.name, kwargs)
        try:
            return await self.coordinator.device.http_request(
                "get", f"thermostat/{self._channel}", kwargs
            )
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

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (current_temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        # Shelly TRV accepts target_t in Fahrenheit or Celsius, but you must
        # send the units that the device expects
        if self.block is not None and self.block.channel is not None:
            therm = self.coordinator.device.settings["thermostats"][
                int(self.block.channel)
            ]
            LOGGER.debug("Themostat settings: %s", therm)
            if therm.get("target_t", {}).get("units", "C") == "F":
                current_temp = TemperatureConverter.convert(
                    cast(float, current_temp),
                    UnitOfTemperature.CELSIUS,
                    UnitOfTemperature.FAHRENHEIT,
                )

        await self.set_state_full_path(target_t_enabled=1, target_t=f"{current_temp}")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        if hvac_mode == HVACMode.OFF:
            if isinstance(self.target_temperature, float):
                self._last_target_temp = self.target_temperature
            await self.set_state_full_path(
                target_t_enabled=1, target_t=f"{self._attr_min_temp}"
            )
        if hvac_mode == HVACMode.HEAT:
            await self.set_state_full_path(
                target_t_enabled=1, target_t=self._last_target_temp
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if not self._preset_modes:
            return

        preset_index = self._preset_modes.index(preset_mode)

        if preset_index == 0:
            await self.set_state_full_path(schedule=0)
        else:
            await self.set_state_full_path(
                schedule=1, schedule_profile=f"{preset_index}"
            )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        LOGGER.info("Restoring entity %s", self.name)

        last_state = await self.async_get_last_state()
        if last_state is not None:
            self.last_state = last_state
            self.last_state_attributes = self.last_state.attributes
            self._preset_modes = cast(
                list, self.last_state.attributes.get("preset_modes")
            )

        last_extra_data = await self.async_get_last_extra_data()
        if last_extra_data is not None:
            self._last_target_temp = last_extra_data.as_dict()["last_target_temp"]

        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle device update."""
        if not self.coordinator.device.initialized:
            self.async_write_ha_state()
            return

        if self.coordinator.device.status.get("calibrated") is False:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                NOT_CALIBRATED_ISSUE_ID.format(unique=self.coordinator.mac),
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="device_not_calibrated",
                translation_placeholders={
                    "device_name": self.coordinator.name,
                    "ip_address": self.coordinator.device.ip_address,
                },
            )
        else:
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                NOT_CALIBRATED_ISSUE_ID.format(unique=self.coordinator.mac),
            )

        assert self.coordinator.device.blocks

        for block in self.coordinator.device.blocks:
            if block.type == "device":
                self.device_block = block
            if hasattr(block, "targetTemp"):
                self.block = block

        if self.device_block and self.block:
            LOGGER.debug("Entity %s attached to blocks", self.name)

            assert self.block.channel

            try:
                self._preset_modes = [
                    PRESET_NONE,
                    *self.coordinator.device.settings["thermostats"][
                        int(self.block.channel)
                    ]["schedule_profile_names"],
                ]
            except InvalidAuthError:
                self.hass.async_create_task(
                    self.coordinator.async_shutdown_device_and_start_reauth(),
                    eager_start=True,
                )
            else:
                self.async_write_ha_state()


class RpcClimate(ShellyRpcEntity, ClimateEntity):
    """Entity that controls a thermostat on RPC based Shelly devices."""

    _attr_max_temp = RPC_THERMOSTAT_SETTINGS["max"]
    _attr_min_temp = RPC_THERMOSTAT_SETTINGS["min"]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = RPC_THERMOSTAT_SETTINGS["step"]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: ShellyRpcCoordinator, id_: int) -> None:
        """Initialize."""
        super().__init__(coordinator, f"thermostat:{id_}")
        self._id = id_
        self._thermostat_type = coordinator.device.config[f"thermostat:{id_}"].get(
            "type", "heating"
        )
        if self._thermostat_type == "cooling":
            self._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]
        else:
            self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        self._humidity_key: str | None = None
        # Check if there is a corresponding humidity key for the thermostat ID
        if (humidity_key := f"humidity:{id_}") in self.coordinator.device.status:
            self._humidity_key = humidity_key

    @property
    def target_temperature(self) -> float | None:
        """Set target temperature."""
        return cast(float, self.status["target_C"])

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return cast(float, self.status["current_C"])

    @property
    def current_humidity(self) -> float | None:
        """Return current humidity."""
        if self._humidity_key is None:
            return None

        return cast(float, self.coordinator.device.status[self._humidity_key]["rh"])

    @property
    def hvac_mode(self) -> HVACMode:
        """HVAC current mode."""
        if not self.status["enable"]:
            return HVACMode.OFF

        return HVACMode.COOL if self._thermostat_type == "cooling" else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """HVAC current action."""
        if not self.status["output"]:
            return HVACAction.IDLE

        return (
            HVACAction.COOLING
            if self._thermostat_type == "cooling"
            else HVACAction.HEATING
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (target_temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        await self.call_rpc(
            "Thermostat.SetConfig",
            {"config": {"id": self._id, "target_C": target_temp}},
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        mode = hvac_mode in (HVACMode.COOL, HVACMode.HEAT)
        await self.call_rpc(
            "Thermostat.SetConfig", {"config": {"id": self._id, "enable": mode}}
        )


class RpcBluTrvClimate(ShellyRpcEntity, ClimateEntity):
    """Entity that controls a thermostat on RPC based Shelly devices."""

    _attr_max_temp = BLU_TRV_TEMPERATURE_SETTINGS["max"]
    _attr_min_temp = BLU_TRV_TEMPERATURE_SETTINGS["min"]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_target_temperature_step = BLU_TRV_TEMPERATURE_SETTINGS["step"]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True

    def __init__(self, coordinator: ShellyRpcCoordinator, id_: int) -> None:
        """Initialize."""

        super().__init__(coordinator, f"{BLU_TRV_IDENTIFIER}:{id_}")
        self._id = id_
        self._config = coordinator.device.config[f"{BLU_TRV_IDENTIFIER}:{id_}"]
        ble_addr: str = self._config["addr"]
        self._attr_unique_id = f"{ble_addr}-{self.key}"
        name = self._config["name"] or f"shellyblutrv-{ble_addr.replace(':', '')}"
        model_id = self._config.get("local_name")
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, ble_addr)},
            identifiers={(DOMAIN, ble_addr)},
            via_device=(DOMAIN, self.coordinator.mac),
            manufacturer="Shelly",
            model=BLU_TRV_MODEL_NAME.get(model_id),
            model_id=model_id,
            name=name,
        )
        # Added intentionally to the constructor to avoid double name from base class
        self._attr_name = None

    @property
    def target_temperature(self) -> float | None:
        """Set target temperature."""
        if not self._config["enable"]:
            return None

        return cast(float, self.status["target_C"])

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return cast(float, self.status["current_C"])

    @property
    def hvac_action(self) -> HVACAction:
        """HVAC current action."""
        if not self.status["pos"]:
            return HVACAction.IDLE

        return HVACAction.HEATING

    @rpc_call
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (target_temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        await self.coordinator.device.blu_trv_set_target_temperature(
            self._id, target_temp
        )
