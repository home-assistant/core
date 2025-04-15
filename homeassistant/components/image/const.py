"""Constants for the image integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import ImageEntity


DOMAIN: Final = "image"
DATA_COMPONENT: HassKey[EntityComponent[ImageEntity]] = HassKey(DOMAIN)

IMAGE_TIMEOUT: Final = 10
