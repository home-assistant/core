"""Constants for the air_quality entity platform."""

from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import AirQualityEntity


DOMAIN: Final = "air_quality"
DATA_COMPONENT: HassKey[EntityComponent[AirQualityEntity]] = HassKey(DOMAIN)
