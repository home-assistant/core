import logging
from frisquet_connect.const import (
    CLIMATE_TRANSLATIONS_KEY,
    ZoneMode,
    ZoneSelector,
)
from frisquet_connect.domains.site.zone import Zone
from frisquet_connect.entities.climate.utils import (
    get_hvac_and_preset_mode_for_a_zone,
    get_target_temperature,
)
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)


from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_SLEEP,
    PRESET_HOME,
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_NONE,
)

from frisquet_connect.entities.core_entity import CoreEntity

_LOGGER = logging.getLogger(__name__)


class DefaultClimateEntity(CoreEntity, ClimateEntity):
    _zone_label_id: str

    def __init__(
        self, coordinator: FrisquetConnectCoordinator, zone_label_id: str
    ) -> None:
        super().__init__(coordinator)

        self._zone_label_id = zone_label_id

        self._attr_unique_id = (
            f"{coordinator.data.site_id}_{CLIMATE_TRANSLATIONS_KEY}_{zone_label_id}"
        )
        self._attr_has_entity_name = True
        self._attr_translation_key = CLIMATE_TRANSLATIONS_KEY
        self._attr_translation_placeholders = {"zone_name": self.zone.name}

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )
        self._attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]

        self._attr_temperature_unit = "°C"
        self._attr_target_temperature_low = 5
        self._attr_target_temperature_high = 25

    @property
    def zone(self) -> Zone:
        return self.coordinator.data.get_zone_by_label_id(self._zone_label_id)

    def update(self) -> None:
        (available_preset_modes, preset_mode, hvac_mode) = (
            get_hvac_and_preset_mode_for_a_zone(self.zone)
        )
        self._attr_preset_modes = available_preset_modes
        self._attr_preset_mode = preset_mode
        self._attr_hvac_mode = hvac_mode

        self._attr_current_temperature = self.zone.detail.current_temperature
        self._attr_target_temperature = get_target_temperature(self.zone)
        if self.zone.detail.target_temperature != get_target_temperature(self.zone):
            _LOGGER.warning(
                f"Current target temperature '{self.zone.detail.target_temperature}' is not (yet) the same as the one predefined in the {self.zone.name}: '{get_target_temperature(self.zone)}'"
            )

    async def async_turn_on(self):
        await self.coordinator.service.async_set_selector(
            self.coordinator.data.site_id, self.zone, ZoneSelector.AUTO
        )

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        await self.coordinator.service.async_set_selector(
            self.coordinator.data.site_id, self.zone, ZoneSelector.FROST_PROTECTION
        )

        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        selector: ZoneSelector
        if hvac_mode == HVACMode.AUTO:
            selector = ZoneSelector.AUTO
        elif hvac_mode == HVACMode.HEAT:
            if self.preset_mode == PRESET_HOME:
                selector = ZoneSelector.COMFORT_PERMANENT
            else:
                selector = ZoneSelector.REDUCED_PERMANENT
        elif hvac_mode == HVACMode.OFF:
            # TODO : non utile si turn_off possible
            selector = ZoneSelector.FROST_PROTECTION
        else:
            _LOGGER.error(f"Unknown HVAC mode '{hvac_mode}'")
            raise ValueError(f"Unknown HVAC mode '{hvac_mode}'")

        await self.coordinator.service.async_set_selector(
            self.coordinator.data.site_id, self.zone, selector
        )
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str):
        current_zone = self.zone
        if preset_mode == PRESET_BOOST:
            # TODO: Only available when the zone is in COMFORT mode
            await self.coordinator.service.async_enable_boost(
                self.coordinator.data.site_id, self.zone
            )
        elif preset_mode == PRESET_HOME:
            # TODO: Only available when HVACMode is in AUTO mode and the zone is in REDUCED mode or BOOST mode
            # TODO: If boost is active, it must be disabled before
            await self.coordinator.service.async_set_exemption(
                self.coordinator.data.site_id, ZoneMode.COMFORT
            )
        elif preset_mode == PRESET_AWAY:
            # TODO: Only available when HVACMode is in AUTO mode and the zone is in COMFORT mode
            # TODO: If boost is active, it must be disabled before
            await self.coordinator.service.async_set_exemption(
                self.coordinator.data.site_id, ZoneMode.REDUCED
            )
        elif preset_mode == PRESET_COMFORT:
            # TODO: Only available when HVACMode is in HEAT mode
            await self.coordinator.service.async_set_selector(
                self.coordinator.data.site_id,
                current_zone,
                ZoneSelector.COMFORT_PERMANENT,
            )
        elif preset_mode == PRESET_SLEEP:
            # TODO: Only available when HVACMode is in HEAT mode
            await self.coordinator.service.async_set_selector(
                self.coordinator.data.site_id,
                current_zone,
                ZoneSelector.REDUCED_PERMANENT,
            )
        elif preset_mode == PRESET_ECO:
            # TODO: Only available when HVACMode is in OFF mode
            await self.coordinator.service.async_set_selector(
                self.coordinator.data.site_id,
                current_zone,
                ZoneSelector.FROST_PROTECTION,
            )
        elif preset_mode == PRESET_NONE:
            # TODO: Only available when HVACMode is in AUTO mode
            if self.zone.detail.is_boosting:
                await self.coordinator.service.async_disable_boost(
                    self.coordinator.data.site_id, self.zone
                )
            elif self.zone.detail.is_exemption_enabled:
                await self.coordinator.service.async_cancel_exemption(
                    self.coordinator.data.site_id
                )
            else:
                await self.coordinator.service.async_set_selector(
                    self.coordinator.data.site_id, current_zone, ZoneSelector.AUTO
                )
        else:
            _LOGGER.error(f"Unknown preset mode '{preset_mode}'")
            raise ValueError(f"Unknown preset mode '{preset_mode}'")

        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs):
        temperature = kwargs.get("temperature")
        await self.coordinator.service.async_set_temperature(
            self.coordinator.data.site_id, self.zone, temperature
        )

        # Update the target temperature attribute to reflect the new value
        # This is necessary because the coordinator may not have updated the data yet
        # and we want to ensure that the UI reflects the new target temperature immediately
        self._attr_target_temperature = temperature

        await self.coordinator.async_request_refresh()
