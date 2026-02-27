"""Select platform for madVR Envy."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from madvr_envy.integration_bridge import (
    ProfileOption,
    build_profile_options as lib_build_profile_options,
    parse_profile_id as lib_parse_profile_id,
)

from .entity import MadvrEnvyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    entities: list[MadvrEnvyEntity] = [
        MadvrEnvyPowerModeSelect(coordinator),
        MadvrEnvyActiveProfileSelect(coordinator),
    ]

    profile_groups = coordinator.data.get("profile_groups", {}) if coordinator.data else {}
    if isinstance(profile_groups, dict):
        for group_id in profile_groups:
            if not isinstance(group_id, str):
                continue
            entities.append(MadvrEnvyProfileGroupSelect(coordinator, group_id))

    async_add_entities(entities)


class MadvrEnvyPowerModeSelect(MadvrEnvyEntity, SelectEntity):
    """Select target power mode."""

    _attr_translation_key = "power_mode"
    _attr_icon = "mdi:power-settings"
    _attr_options = ["on", "standby", "off"]

    def __init__(self, coordinator) -> None:  # noqa: ANN001
        super().__init__(coordinator, "power_mode")

    @property
    def current_option(self) -> str | None:
        power_state = self.data.get("power_state")
        if isinstance(power_state, str) and power_state in self.options:
            return power_state
        return None

    async def async_select_option(self, option: str) -> None:
        if option == "on":
            await self._execute("KeyPress POWER", lambda: self._client.key_press("POWER"))
            return
        if option == "standby":
            await self._execute("Standby", self._client.standby)
            return
        if option == "off":
            await self._execute("PowerOff", self._client.power_off)


class MadvrEnvyActiveProfileSelect(MadvrEnvyEntity, SelectEntity):
    """Select active profile by group/index."""

    _attr_translation_key = "active_profile"
    _attr_icon = "mdi:format-list-bulleted"

    def __init__(self, coordinator) -> None:  # noqa: ANN001
        super().__init__(coordinator, "active_profile")

    @property
    def options(self) -> list[str]:
        return [entry.option for entry in self._profile_options]

    @property
    def current_option(self) -> str | None:
        active_group = self.data.get("active_profile_group")
        active_index = self.data.get("active_profile_index")
        if not isinstance(active_group, str) or not isinstance(active_index, int):
            return None

        for entry in self._profile_options:
            if entry.group_id == active_group and entry.profile_index == active_index:
                return entry.option
        return None

    async def async_select_option(self, option: str) -> None:
        for entry in self._profile_options:
            if entry.option == option:
                await self._execute(
                    f"ActivateProfile {entry.group_id}/{entry.profile_index}",
                    lambda group_id=entry.group_id, profile_index=entry.profile_index: (
                        self._client.activate_profile(group_id, profile_index)
                    ),
                )
                return

    @property
    def _profile_options(self) -> list[ProfileOption]:
        return _build_profile_options(self.data)


class MadvrEnvyProfileGroupSelect(MadvrEnvyEntity, SelectEntity):
    """Select active profile for a specific profile group."""

    _attr_icon = "mdi:playlist-edit"

    def __init__(self, coordinator, group_id: str) -> None:  # noqa: ANN001
        self._group_id = group_id
        super().__init__(coordinator, f"profile_group_{group_id}")

    @property
    def name(self) -> str:
        group_names = self.data.get("profile_groups")
        label = self._group_id
        if not isinstance(group_names, dict):
            return f"{label} Profile"
        value = group_names.get(self._group_id)
        if isinstance(value, str) and value:
            label = value
        return f"{label} Profile"

    @property
    def options(self) -> list[str]:
        return [entry.option for entry in self._group_options]

    @property
    def current_option(self) -> str | None:
        active_group = self.data.get("active_profile_group")
        active_index = self.data.get("active_profile_index")
        if active_group != self._group_id or not isinstance(active_index, int):
            return None
        for entry in self._group_options:
            if entry.profile_index == active_index:
                return entry.option
        return None

    async def async_select_option(self, option: str) -> None:
        for entry in self._group_options:
            if entry.option != option:
                continue
            await self._execute(
                f"ActivateProfile {self._group_id}/{entry.profile_index}",
                lambda profile_index=entry.profile_index: self._client.activate_profile(
                    self._group_id, profile_index
                ),
            )
            return

    @property
    def _group_options(self) -> list[ProfileOption]:
        all_options = _build_profile_options(self.data)
        return [entry for entry in all_options if entry.group_id == self._group_id]


def _parse_profile_id(profile_id: str, fallback_group: object) -> tuple[str, int] | None:
    return lib_parse_profile_id(profile_id, fallback_group)


def _build_profile_options(data: dict[str, object]) -> list[ProfileOption]:
    return lib_build_profile_options(data)
