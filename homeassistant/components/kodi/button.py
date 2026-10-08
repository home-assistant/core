"""Kodi playback delay and display reset buttons."""

from math import isclose, isfinite
from typing import Any, Literal, override

from jsonrpc_base.jsonrpc import ProtocolError, TransportError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KodiConfigEntry
from .const import DOMAIN
from .coordinator import KodiPlaybackCoordinator
from .entity import KodiPlaybackEntity

BUTTONS = (
    ButtonEntityDescription(
        key="reset_picture_position", translation_key="reset_picture_position"
    ),
    ButtonEntityDescription(
        key="reset_subtitle_position", translation_key="reset_subtitle_position"
    ),
)


class KodiDelayButtonDescription(ButtonEntityDescription, frozen_or_thawed=True):
    """Describe an audio or subtitle delay action."""

    delay_type: Literal["audio", "subtitle"] = "audio"
    action: Literal["increase", "decrease", "reset"] = "reset"


DELAY_BUTTONS = (
    KodiDelayButtonDescription(
        key="increase_audio_delay",
        translation_key="increase_audio_delay",
        delay_type="audio",
        action="increase",
    ),
    KodiDelayButtonDescription(
        key="decrease_audio_delay",
        translation_key="decrease_audio_delay",
        delay_type="audio",
        action="decrease",
    ),
    KodiDelayButtonDescription(
        key="reset_audio_delay",
        translation_key="reset_audio_delay",
        delay_type="audio",
        action="reset",
    ),
    KodiDelayButtonDescription(
        key="increase_subtitle_delay",
        translation_key="increase_subtitle_delay",
        delay_type="subtitle",
        action="increase",
    ),
    KodiDelayButtonDescription(
        key="decrease_subtitle_delay",
        translation_key="decrease_subtitle_delay",
        delay_type="subtitle",
        action="decrease",
    ),
    KodiDelayButtonDescription(
        key="reset_subtitle_delay",
        translation_key="reset_subtitle_delay",
        delay_type="subtitle",
        action="reset",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KodiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kodi display reset and delay buttons."""
    async_add_entities(
        [
            *(
                KodiDisplayResetButton(entry.runtime_data.playback, description)
                for description in BUTTONS
            ),
            *(
                KodiPlaybackDelayButton(entry.runtime_data.playback, description)
                for description in DELAY_BUTTONS
            ),
        ]
    )


class KodiDisplayResetButton(KodiPlaybackEntity, ButtonEntity):
    """Reset picture vertical shift or subtitle margin to its neutral value."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: KodiPlaybackCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the reset button."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Picture reset requires video; subtitle margin is a global setting."""
        if self.entity_description.key == "reset_picture_position":
            return super().available and (
                self.coordinator.data.get("player", {}).get("type") == "video"
                and self.coordinator.data.get("viewmode") is not None
            )
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.get("subtitle_margin") is not None
        )

    @override
    async def async_press(self) -> None:
        """Restore the picture center or Kodi's configured subtitle default."""
        await self.coordinator.async_refresh()
        if not self.available:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="display_unavailable"
            )
        try:
            if self.entity_description.key == "reset_picture_position":
                viewmode: dict[str, Any] = {
                    key: setting
                    for key, setting in self.coordinator.data["viewmode"].items()
                    if key in ("zoom", "pixelratio", "nonlinearstretch")
                }
                viewmode["verticalshift"] = 0.0
                await self.coordinator.kodi.call_method(
                    "Player.SetViewMode", viewmode=viewmode
                )
            else:
                default = await self.coordinator.async_get_setting_default(
                    "subtitles.marginvertical"
                )
                accepted = await self.coordinator.kodi.call_method(
                    "Settings.SetSettingValue",
                    setting="subtitles.marginvertical",
                    value=default,
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


class KodiPlaybackDelayButton(KodiPlaybackEntity, ButtonEntity):
    """Change or reset an active Kodi playback delay."""

    entity_description: KodiDelayButtonDescription

    def __init__(
        self,
        coordinator: KodiPlaybackCoordinator,
        description: KodiDelayButtonDescription,
    ) -> None:
        """Initialize the delay control."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Require an active video and a readable delay value."""
        key = f"{self.entity_description.delay_type}_delay"
        return (
            super().available
            and self.coordinator.data.get("player", {}).get("type") == "video"
            and self.coordinator.data.get(key) is not None
        )

    @override
    async def async_press(self) -> None:
        """Adjust by Kodi's configured step or reset the offset to zero."""
        await self.coordinator.async_refresh()
        if not self.available:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="playback_unavailable"
            )

        description = self.entity_description
        try:
            if description.delay_type == "audio":
                await self._async_adjust_audio_delay()
            elif description.action == "reset":
                await self._async_reset_delay("subtitle")
            else:
                await self._async_execute_delay_action(
                    self._get_action_name("subtitle", description.action)
                )
        except (TransportError, ProtocolError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="delay_change_failed"
            ) from err
        await self.coordinator.async_refresh()

    async def _async_adjust_audio_delay(self) -> None:
        """Use Player.SetAudioDelay, with actions for older Kodi versions."""
        description = self.entity_description
        player_id = self.coordinator.data["player"]["playerid"]
        offsets: dict[str, int | str] = {
            "increase": "increment",
            "decrease": "decrement",
            "reset": 0,
        }
        offset = offsets[description.action]
        try:
            await self.coordinator.kodi.call_method(
                "Player.SetAudioDelay", playerid=player_id, offset=offset
            )
        except ProtocolError:
            if description.action == "reset":
                await self._async_reset_delay("audio")
            else:
                await self._async_execute_delay_action(
                    self._get_action_name("audio", description.action)
                )

    async def _async_reset_delay(
        self, delay_type: Literal["audio", "subtitle"]
    ) -> None:
        """Use Kodi's relative actions when no absolute setter is available."""
        current = self.coordinator.data[f"{delay_type}_delay"]
        if isclose(current, 0, abs_tol=0.0005):
            return

        action = self._get_action_name(
            delay_type, "decrease" if current > 0 else "increase"
        )
        await self._async_execute_delay_action(action)
        updated = await self._async_get_delay(delay_type)
        if isclose(updated, 0, abs_tol=0.0005):
            return
        if not isfinite(current) or not isfinite(updated):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="delay_reset_failed"
            )
        step = abs(current - updated)
        if not step:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="delay_reset_failed"
            )
        remaining = round(abs(updated) / step)
        if (
            not isclose(abs(updated), remaining * step, abs_tol=0.0005)
            or remaining > 1000
        ):
            await self._async_execute_delay_action(
                self._get_action_name(
                    delay_type, "increase" if current > 0 else "decrease"
                )
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="delay_reset_failed"
            )
        for _ in range(remaining):
            await self._async_execute_delay_action(action)
        if not isclose(await self._async_get_delay(delay_type), 0, abs_tol=0.0005):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="delay_reset_failed"
            )

    async def _async_get_delay(self, delay_type: Literal["audio", "subtitle"]) -> float:
        """Read Kodi's current offset after one relative action."""
        label = f"Player.{delay_type.title()}Delay"
        labels = await self.coordinator.kodi.call_method(
            "XBMC.GetInfoLabels", labels=[label]
        )
        try:
            return float(str(labels[label]).removesuffix("s").strip())
        except (KeyError, TypeError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="delay_reset_failed"
            ) from err

    async def _async_execute_delay_action(self, action: str) -> None:
        """Send one relative delay action to Kodi."""
        await self.coordinator.kodi.call_method("Input.ExecuteAction", action=action)

    @staticmethod
    def _get_action_name(
        delay_type: Literal["audio", "subtitle"],
        action: Literal["increase", "decrease"],
    ) -> str:
        """Return Kodi's built-in action for an offset adjustment."""
        suffix = "plus" if action == "increase" else "minus"
        return f"{delay_type}delay{suffix}"
