"""Support for Magic Home select."""
from __future__ import annotations

import asyncio

from flux_led.aio import AIOWifiLedBulb
from flux_led.base_device import DeviceType
from flux_led.const import (
    DEFAULT_WHITE_CHANNEL_TYPE,
    STATE_CHANGE_LATENCY,
    WhiteChannelType,
)
from flux_led.protocol import PowerRestoreState, RemoteConfig

from homeassistant import config_entries
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_WHITE_CHANNEL_TYPE, DOMAIN, FLUX_COLOR_MODE_RGBW
from .coordinator import FluxLedUpdateCoordinator
from .entity import FluxBaseEntity, FluxEntity
from .util import _human_readable_option

NAME_TO_POWER_RESTORE_STATE = {
    _human_readable_option(option.name): option for option in PowerRestoreState
}


async def _async_delayed_reload(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    """Reload after making a change that will effect the operation of the device."""
    await asyncio.sleep(STATE_CHANGE_LATENCY)
    hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flux selects."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    entities: list[
        FluxPowerStateSelect
        | FluxOperatingModesSelect
        | FluxWiringsSelect
        | FluxICTypeSelect
        | FluxRemoteConfigSelect
        | FluxWhiteChannelSelect
    ] = []
    entry.data.get(CONF_NAME, entry.title)
    base_unique_id = entry.unique_id or entry.entry_id

    if device.device_type == DeviceType.Switch:
        entities.append(FluxPowerStateSelect(coordinator.device, entry))
    if device.operating_modes:
        entities.append(
            FluxOperatingModesSelect(coordinator, base_unique_id, "operating_mode")
        )
    if device.wirings and device.wiring is not None:
        entities.append(FluxWiringsSelect(coordinator, base_unique_id, "wiring"))
    if device.ic_types:
        entities.append(FluxICTypeSelect(coordinator, base_unique_id, "ic_type"))
    if device.remote_config:
        entities.append(
            FluxRemoteConfigSelect(coordinator, base_unique_id, "remote_config")
        )
    if FLUX_COLOR_MODE_RGBW in device.color_modes:
        entities.append(FluxWhiteChannelSelect(coordinator.device, entry))

    async_add_entities(entities)


class FluxConfigAtStartSelect(FluxBaseEntity, SelectEntity):
    """Representation of a flux config entity that only updates at start or change."""

    _attr_entity_category = EntityCategory.CONFIG


class FluxConfigSelect(FluxEntity, SelectEntity):
    """Representation of a flux config entity that updates."""

    _attr_entity_category = EntityCategory.CONFIG


class FluxPowerStateSelect(FluxConfigAtStartSelect, SelectEntity):
    """Representation of a Flux power restore state option."""

    _attr_translation_key = "power_restored"
    _attr_icon = "mdi:transmission-tower-off"
    _attr_options = list(NAME_TO_POWER_RESTORE_STATE)

    def __init__(
        self,
        device: AIOWifiLedBulb,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Initialize the power state select."""
        super().__init__(device, entry)
        base_unique_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_unique_id}_power_restored"
        self._async_set_current_option_from_device()

    @callback
    def _async_set_current_option_from_device(self) -> None:
        """Set the option from the current power state."""
        restore_states = self._device.power_restore_states
        assert restore_states is not None
        assert restore_states.channel1 is not None
        self._attr_current_option = _human_readable_option(restore_states.channel1.name)

    async def async_select_option(self, option: str) -> None:
        """Change the power state."""
        await self._device.async_set_power_restore(
            channel1=NAME_TO_POWER_RESTORE_STATE[option]
        )
        self._async_set_current_option_from_device()
        self.async_write_ha_state()


class FluxICTypeSelect(FluxConfigSelect):
    """Representation of Flux ic type."""

    _attr_icon = "mdi:chip"
    _attr_translation_key = "ic_type"

    @property
    def options(self) -> list[str]:
        """Return the available ic types."""
        assert self._device.ic_types is not None
        return self._device.ic_types

    @property
    def current_option(self) -> str | None:
        """Return the current ic type."""
        return self._device.ic_type

    async def async_select_option(self, option: str) -> None:
        """Change the ic type."""
        await self._device.async_set_device_config(ic_type=option)
        await _async_delayed_reload(self.hass, self.coordinator.entry)


class FluxWiringsSelect(FluxConfigSelect):
    """Representation of Flux wirings."""

    _attr_icon = "mdi:led-strip-variant"
    _attr_translation_key = "wiring"

    @property
    def options(self) -> list[str]:
        """Return the available wiring options based on the strip protocol."""
        assert self._device.wirings is not None
        return self._device.wirings

    @property
    def current_option(self) -> str | None:
        """Return the current wiring."""
        return self._device.wiring

    async def async_select_option(self, option: str) -> None:
        """Change the wiring."""
        await self._device.async_set_device_config(wiring=option)


class FluxOperatingModesSelect(FluxConfigSelect):
    """Representation of Flux operating modes."""

    _attr_translation_key = "operating_mode"

    @property
    def options(self) -> list[str]:
        """Return the current operating mode."""
        assert self._device.operating_modes is not None
        return self._device.operating_modes

    @property
    def current_option(self) -> str | None:
        """Return the current operating mode."""
        return self._device.operating_mode

    async def async_select_option(self, option: str) -> None:
        """Change the ic type."""
        await self._device.async_set_device_config(operating_mode=option)
        await _async_delayed_reload(self.hass, self.coordinator.entry)


class FluxRemoteConfigSelect(FluxConfigSelect):
    """Representation of Flux remote config type."""

    _attr_translation_key = "remote_config"

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        base_unique_id: str,
        key: str,
    ) -> None:
        """Initialize the remote config type select."""
        super().__init__(coordinator, base_unique_id, key)
        assert self._device.remote_config is not None
        self._name_to_state = {
            _human_readable_option(option.name): option for option in RemoteConfig
        }
        self._attr_options = list(self._name_to_state)

    @property
    def current_option(self) -> str | None:
        """Return the current remote config."""
        assert self._device.remote_config is not None
        return _human_readable_option(self._device.remote_config.name)

    async def async_select_option(self, option: str) -> None:
        """Change the remote config setting."""
        remote_config: RemoteConfig = self._name_to_state[option]
        await self._device.async_config_remotes(remote_config)


class FluxWhiteChannelSelect(FluxConfigAtStartSelect):
    """Representation of Flux white channel."""

    _attr_translation_key = "white_channel"

    _attr_options = [_human_readable_option(option.name) for option in WhiteChannelType]

    def __init__(
        self,
        device: AIOWifiLedBulb,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Initialize the white channel select."""
        super().__init__(device, entry)
        base_unique_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_unique_id}_white_channel"

    @property
    def current_option(self) -> str | None:
        """Return the current white channel type."""
        return _human_readable_option(
            self.entry.data.get(
                CONF_WHITE_CHANNEL_TYPE, DEFAULT_WHITE_CHANNEL_TYPE.name
            )
        )

    async def async_select_option(self, option: str) -> None:
        """Change the white channel type."""
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={**self.entry.data, CONF_WHITE_CHANNEL_TYPE: option.lower()},
        )
        await _async_delayed_reload(self.hass, self.entry)
