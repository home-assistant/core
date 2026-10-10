"""Constants for the Radio Frequency integration."""

from typing import Final

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

from .entity import RadioFrequencyTransmitterEntity

DOMAIN: Final = "radio_frequency"

DATA_COMPONENT: HassKey[EntityComponent[RadioFrequencyTransmitterEntity]] = HassKey(
    DOMAIN
)
