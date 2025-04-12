"""Support for TPLink siren entity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
from typing import TYPE_CHECKING, Any, cast

from kasa import Device, Module

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    DOMAIN as SIREN_DOMAIN,
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
    SirenTurnOnServiceParameters,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TPLinkConfigEntry, legacy_device_id
from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    CoordinatedTPLinkModuleEntity,
    TPLinkModuleEntityDescription,
    async_refresh_after,
)

# Coordinator is used to centralize the data updates
# For actions the integration handles locking of concurrent device request
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TPLinkSirenEntityDescription(
    SirenEntityDescription, TPLinkModuleEntityDescription
):
    """Base class for siren entity description."""

    unique_id_fn: Callable[[Device, TPLinkModuleEntityDescription], str] = (
        lambda device, desc: legacy_device_id(device)
        if desc.key == "siren"
        else f"{legacy_device_id(device)}-{desc.key}"
    )


SIREN_DESCRIPTIONS: tuple[TPLinkSirenEntityDescription, ...] = (
    TPLinkSirenEntityDescription(
        key="siren",
        exists_fn=lambda dev, _: Module.Alarm in dev.modules,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up siren entities."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    known_child_device_ids: set[str] = set()
    first_check = True

    def _check_device() -> None:
        entities = CoordinatedTPLinkModuleEntity.entities_for_device_and_its_children(
            hass=hass,
            device=device,
            coordinator=parent_coordinator,
            entity_class=TPLinkSirenEntity,
            descriptions=SIREN_DESCRIPTIONS,
            platform_domain=SIREN_DOMAIN,
            known_child_device_ids=known_child_device_ids,
            first_check=first_check,
        )
        async_add_entities(entities)

    _check_device()
    first_check = False
    config_entry.async_on_unload(parent_coordinator.async_add_listener(_check_device))


class TPLinkSirenEntity(CoordinatedTPLinkModuleEntity, SirenEntity):
    """Representation of a tplink siren entity."""

    _attr_name = None
    _attr_supported_features = (
        SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TONES
        | SirenEntityFeature.DURATION
        | SirenEntityFeature.VOLUME_SET
    )

    entity_description: TPLinkSirenEntityDescription

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        description: TPLinkSirenEntityDescription,
        *,
        parent: Device | None = None,
    ) -> None:
        """Initialize the siren entity."""
        super().__init__(device, coordinator, description, parent=parent)
        self._alarm_module = device.modules[Module.Alarm]

        alarm_vol_feat = self._alarm_module.get_feature("alarm_volume")
        alarm_duration_feat = self._alarm_module.get_feature("alarm_duration")
        if TYPE_CHECKING:
            assert alarm_vol_feat
            assert alarm_duration_feat
        self._alarm_volume_max = alarm_vol_feat.maximum_value
        self._alarm_duration_max = alarm_duration_feat.maximum_value

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on."""
        turn_on_params = cast(SirenTurnOnServiceParameters, kwargs)
        if (volume := kwargs.get(ATTR_VOLUME_LEVEL)) is not None:
            # service parameter is a % so we round up to the nearest int
            volume = math.ceil(volume * self._alarm_volume_max)

        if (duration := kwargs.get(ATTR_DURATION)) is not None:
            if duration < 1 or duration > self._alarm_duration_max:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_alarm_duration",
                    translation_placeholders={
                        "duration": str(duration),
                        "duration_max": str(self._alarm_duration_max),
                    },
                )

        await self._alarm_module.play(
            duration=turn_on_params.get(ATTR_DURATION),
            volume=volume,
            sound=kwargs.get(ATTR_TONE),
        )

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        await self._alarm_module.stop()

    @callback
    def _async_update_attrs(self) -> bool:
        """Update the entity's attributes."""
        self._attr_is_on = self._alarm_module.active
        # alarm_sounds returns list[str], so we need to widen the type
        self._attr_available_tones = cast(
            list[str | int], self._alarm_module.alarm_sounds
        )
        return True
