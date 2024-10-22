"""Support for Bryant Evolution HVAC systems."""

import logging
from typing import Any

from evolutionhttp import BryantEvolutionLocalClient

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import CONF_FILENAME, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BryantEvolutionConfigEntry, names
from .const import CONF_SYSTEM_ZONE, DOMAIN
from .coordinator import EvolutionCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BryantEvolutionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""

    # Add a climate entity for each system/zone.
    sam_uid = names.sam_device_uid(config_entry)
    entities: list[Entity] = []

    for sz in config_entry.data[CONF_SYSTEM_ZONE]:
        system_id = sz[0]
        zone_id = sz[1]
        climate = BryantEvolutionClimate(
            await BryantEvolutionLocalClient.get_client(
                system_id, zone_id, config_entry.data[CONF_FILENAME]
            ),
            config_entry.runtime_data,  # coordinator
            system_id,
            zone_id,
            config_entry.data[CONF_FILENAME],
            sam_uid,
        )
        entities.append(climate)
    async_add_entities(entities)


class BryantEvolutionClimate(CoordinatorEntity[EvolutionCoordinator], ClimateEntity):
    """ClimateEntity for Bryant Evolution HVAC systems.

    Design note: this class updates using polling. However, polling
    is very slow (~1500 ms / parameter). To improve the user
    experience on updates, we also locally update this instance and
    call async_write_ha_state as well.
    """

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    ]
    _attr_fan_modes = ["auto", "low", "med", "high"]
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        client: BryantEvolutionLocalClient,
        coordinator: EvolutionCoordinator,
        system_id: int,
        zone_id: int,
        tty: str,
        sam_uid: str,
    ) -> None:
        """Initialize an entity from parts."""
        super().__init__(coordinator)
        self._client = client
        self._system_id = system_id
        self._zone_id = zone_id
        self._tty = tty
        self._attr_name = None
        self._attr_unique_id = names.zone_entity_uid(sam_uid, system_id, zone_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Bryant",
            via_device=(DOMAIN, names.system_device_uid(sam_uid, system_id)),
            name=f"System {system_id} Zone {zone_id}",
        )
        self._set_attrs_from_coordinator()

    def _set_attrs_from_coordinator(self) -> None:
        # Propagate some parameters that are really system-level, not zone-level,
        # but that the climate entity needs.
        self._attr_fan_mode = self.coordinator.data.read_fan_mode(self._system_id)
        self._attr_hvac_mode = self.coordinator.data.read_hvac_mode(self._system_id)

        # Read the zone-level parameters.
        self._attr_current_temperature = self.coordinator.data.read_current_temperature(
            self._system_id, self._zone_id
        )
        (
            self._attr_target_temperature,
            self._attr_target_temperature_low,
            self._attr_target_temperature_high,
        ) = self.coordinator.data.read_target_temperatures(
            self._system_id, self._zone_id
        )
        self._attr_hvac_action = self.coordinator.data.read_hvac_action(
            self._system_id, self._zone_id
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_attrs_from_coordinator()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.HEAT_COOL:
            hvac_mode = HVACMode.AUTO
        if not await self._client.set_hvac_mode(hvac_mode):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="failed_to_set_hvac_mode"
            )
        self._attr_hvac_mode = hvac_mode
        self._async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if kwargs.get("target_temp_high"):
            temp = int(kwargs["target_temp_high"])
            if not await self._client.set_cooling_setpoint(temp):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="failed_to_set_clsp"
                )
            self._attr_target_temperature_high = temp

        if kwargs.get("target_temp_low"):
            temp = int(kwargs["target_temp_low"])
            if not await self._client.set_heating_setpoint(temp):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="failed_to_set_htsp"
                )
            self._attr_target_temperature_low = temp

        if kwargs.get("temperature"):
            temp = int(kwargs["temperature"])
            fn = (
                self._client.set_heating_setpoint
                if self.hvac_mode == HVACMode.HEAT
                else self._client.set_cooling_setpoint
            )
            if not await fn(temp):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="failed_to_set_temp"
                )
            self._attr_target_temperature = temp

        # If we get here, we must have changed something unless HA allowed an
        # invalid service call (without any recognized kwarg).
        self._async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if not await self._client.set_fan_mode(fan_mode):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="failed_to_set_fan_mode"
            )
        self._attr_fan_mode = fan_mode.lower()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
