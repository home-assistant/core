"""Support for ZHA sirens."""

import functools
from typing import Any

from zha.application.platforms.siren import (
    SirenEntityFeature as ZHASirenEntityFeature,
    WarningMode,
)

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
    async_add_entities as zha_async_add_entities,
    convert_zha_error_to_ha_error,
    get_zha_data,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation siren from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.SIREN]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, ZHASiren, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class ZHASiren(ZHAEntity, SirenEntity):
    """Representation of a ZHA siren."""

    _attr_available_tones: list[int | str] | dict[int, str] | None = {
        WarningMode.Burglar: "Burglar",
        WarningMode.Fire: "Fire",
        WarningMode.Emergency: "Emergency",
        WarningMode.Police_Panic: "Police Panic",
        WarningMode.Fire_Panic: "Fire Panic",
        WarningMode.Emergency_Panic: "Emergency Panic",
    }

    def __init__(self, entity_data: EntityData, **kwargs: Any) -> None:
        """Initialize the ZHA siren."""
        super().__init__(entity_data, **kwargs)

        features: SirenEntityFeature = SirenEntityFeature(0)
        zha_features: ZHASirenEntityFeature = self.entity_data.entity.supported_features

        if ZHASirenEntityFeature.TURN_ON in zha_features:
            features |= SirenEntityFeature.TURN_ON
        if ZHASirenEntityFeature.TURN_OFF in zha_features:
            features |= SirenEntityFeature.TURN_OFF
        if ZHASirenEntityFeature.TONES in zha_features:
            features |= SirenEntityFeature.TONES
        if ZHASirenEntityFeature.VOLUME_SET in zha_features:
            features |= SirenEntityFeature.VOLUME_SET
        if ZHASirenEntityFeature.DURATION in zha_features:
            features |= SirenEntityFeature.DURATION

        self._attr_supported_features = features

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.entity_data.entity.is_on

    @convert_zha_error_to_ha_error()
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on siren."""
        await self.entity_data.entity.async_turn_on(
            duration=kwargs.get(ATTR_DURATION),
            tone=kwargs.get(ATTR_TONE),
            volume_level=kwargs.get(ATTR_VOLUME_LEVEL),
        )
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off siren."""
        await self.entity_data.entity.async_turn_off()
        self.async_write_ha_state()
