"""Component to interface with various sirens/chimes."""

from datetime import timedelta
import logging
from typing import Any, final, override

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry

# The SERVICE_* constants are re-exported for integrations importing them from
# the siren component root.
from homeassistant.const import (  # noqa: F401
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_AVAILABLE_TONES,
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    DATA_COMPONENT,
    DOMAIN,
    SirenEntityCapabilityAttribute,
    SirenEntityFeature,
)
from .services import (  # noqa: F401
    TURN_ON_SCHEMA,
    SirenTurnOnServiceParameters,
    async_setup_services,
    process_turn_on_params,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)


# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up siren devices."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[SirenEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class SirenEntityDescription(ToggleEntityDescription, frozen_or_thawed=True):
    """A class that describes siren entities."""

    available_tones: list[int | str] | dict[int, str] | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "available_tones",
    "supported_features",
}


class SirenEntity(ToggleEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of a siren device."""

    _entity_component_unrecorded_attributes = frozenset(
        {SirenEntityCapabilityAttribute.AVAILABLE_TONES}
    )

    entity_description: SirenEntityDescription
    _attr_available_tones: list[int | str] | dict[int, str] | None
    _attr_supported_features: SirenEntityFeature = SirenEntityFeature(0)

    @final
    @property
    @override
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return capability attributes."""
        if (
            self.supported_features & SirenEntityFeature.TONES
            and self.available_tones is not None
        ):
            return {
                SirenEntityCapabilityAttribute.AVAILABLE_TONES: self.available_tones
            }

        return None

    @cached_property
    def available_tones(self) -> list[int | str] | dict[int, str] | None:
        """Return a list of available tones.

        Requires SirenEntityFeature.TONES.
        """
        if hasattr(self, "_attr_available_tones"):
            return self._attr_available_tones
        if hasattr(self, "entity_description"):
            return self.entity_description.available_tones
        return None

    @cached_property
    @override
    def supported_features(self) -> SirenEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features
