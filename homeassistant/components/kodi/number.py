"""Kodi picture shift and subtitle display controls."""

import math
from typing import override

from jsonrpc_base.jsonrpc import ProtocolError, TransportError

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KodiConfigEntry
from .const import DOMAIN
from .coordinator import KodiPlaybackCoordinator
from .entity import KodiPlaybackEntity

NUMBERS = (
    NumberEntityDescription(
        key="picture_vertical_shift",
        translation_key="picture_vertical_shift",
        native_min_value=-2.0,
        native_max_value=2.0,
        native_step=0.01,
        mode=NumberMode.SLIDER,
    ),
    NumberEntityDescription(
        key="subtitle_margin",
        translation_key="subtitle_margin",
        native_min_value=0,
        native_max_value=50,
        native_step=0.05,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
    ),
    NumberEntityDescription(
        key="subtitle_opacity",
        translation_key="subtitle_opacity",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KodiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Kodi number controls."""
    async_add_entities(
        KodiPlaybackNumber(entry.runtime_data.playback, description)
        for description in NUMBERS
    )


class KodiPlaybackNumber(KodiPlaybackEntity, NumberEntity):
    """Control a picture parameter or global subtitle setting."""

    entity_description: NumberEntityDescription

    def __init__(
        self, coordinator: KodiPlaybackCoordinator, description: NumberEntityDescription
    ) -> None:
        """Initialize the number control."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Global subtitle settings work online; picture shift needs video."""
        if not self.coordinator.last_update_success or self.native_value is None:
            return False
        return (
            self.entity_description.key in ("subtitle_opacity", "subtitle_margin")
            or self.coordinator.data.get("player", {}).get("type") == "video"
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the reported setting, without optimistic state changes."""
        value = self.coordinator.data.get(self.entity_description.key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        if self.entity_description.key == "picture_vertical_shift":
            return round(value, 2)
        return value

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Validate, set the control, and read back Kodi's value."""
        description = self.entity_description
        assert description.native_min_value is not None
        assert description.native_max_value is not None
        assert description.native_step is not None
        if (
            not math.isfinite(value)
            or not description.native_min_value <= value <= description.native_max_value
            or (description.key == "subtitle_opacity" and not float(value).is_integer())
            or (
                description.key == "subtitle_margin"
                and not math.isclose(
                    value / description.native_step,
                    round(value / description.native_step),
                    abs_tol=1e-7,
                )
            )
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_display_value"
            )
        await self.coordinator.async_refresh()
        if not self.available:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="display_unavailable"
            )
        try:
            if description.key == "picture_vertical_shift":
                viewmode = {
                    key: setting
                    for key, setting in self.coordinator.data["viewmode"].items()
                    if key in ("zoom", "pixelratio", "nonlinearstretch")
                }
                viewmode["verticalshift"] = float(value)
                await self.coordinator.kodi.call_method(
                    "Player.SetViewMode", viewmode=viewmode
                )
            elif description.key == "subtitle_margin":
                accepted = await self.coordinator.kodi.call_method(
                    "Settings.SetSettingValue",
                    setting="subtitles.marginvertical",
                    value=float(value),
                )
                if accepted is not True:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="display_change_failed",
                    )
            else:
                accepted = await self.coordinator.kodi.call_method(
                    "Settings.SetSettingValue",
                    setting="subtitles.opacity",
                    value=int(value),
                )
                if accepted is not True:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="display_change_failed",
                    )
        except (TransportError, ProtocolError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="display_change_failed"
            ) from err
        await self.coordinator.async_refresh()
