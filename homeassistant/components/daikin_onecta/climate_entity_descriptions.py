"""Climate entity descriptions for the Daikin Onecta integration."""

from homeassistant.components.climate import ClimateEntityDescription

CLIMATE_ENTITY_DESCRIPTIONS: dict[str, ClimateEntityDescription] = {
    "calculatedLeavingWaterTemperature": ClimateEntityDescription(
        key="calculated_leaving_water_temperature",
        translation_key="calculated_leaving_water_temperature",
    ),
    "leavingWaterOffset": ClimateEntityDescription(
        key="leaving_water_offset",
        translation_key="leaving_water_offset",
    ),
    "leavingWaterTemperature": ClimateEntityDescription(
        key="leaving_water_temperature",
        translation_key="leaving_water_temperature",
    ),
    "roomTemperature": ClimateEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
    ),
}

CLIMATE_SETPOINT_TYPES = frozenset(CLIMATE_ENTITY_DESCRIPTIONS)
