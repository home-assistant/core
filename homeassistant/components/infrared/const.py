"""Constants for the Infrared integration."""

from typing import Final

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

from .entity import InfraredEmitterEntity, InfraredReceiverEntity

DOMAIN: Final = "infrared"
DATA_COMPONENT: HassKey[
    EntityComponent[InfraredEmitterEntity | InfraredReceiverEntity]
] = HassKey(DOMAIN)
