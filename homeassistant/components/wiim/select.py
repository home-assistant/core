"""Audio output selection for WiiM devices."""

from typing import override

import aiohttp
from async_upnp_client.exceptions import UpnpError
from wiim.exceptions import WiimException
from wiim.wiim_device import WiimDevice

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    LOGGER,
    SIGNAL_DEVICE_GENERAL_UPDATED,
    SIGNAL_DEVICE_RENDERING_CONTROL_UPDATED,
    WiimConfigEntry,
)
from .entity import WiimBaseEntity

PARALLEL_UPDATES = 1

OTHER_OUTPUT = "other_out"


def _normalize_output_mode(mode: str | None) -> str | None:
    """Map the SDK fallback label to its translation key."""
    return OTHER_OUTPUT if mode == "Other Out" else mode


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WiimConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the device's audio output selector."""
    if not entry.runtime_data.supports_http_api:
        return

    async_add_entities([WiimOutputSelect(entry.runtime_data)], True)


class WiimOutputSelect(WiimBaseEntity, SelectEntity):
    """Select an audio output reported by the device."""

    _attr_translation_key = "audio_output"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(self, device: WiimDevice) -> None:
        """Initialize the audio output selector."""
        super().__init__(device)
        self._attr_unique_id = f"{device.udn}_audio_output"
        self._attr_options = [
            mode
            for mode in device.supported_output_modes
            if _normalize_output_mode(mode) != OTHER_OUTPUT
        ]
        current = _normalize_output_mode(device.output_mode)
        self._attr_current_option = current if current in self._attr_options else None

    @property
    @override
    def available(self) -> bool:
        """Return whether a supported output can be selected."""
        return super().available and bool(self._attr_options)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to device updates from the config-entry event bridge."""
        await super().async_added_to_hass()
        for signal in (
            SIGNAL_DEVICE_GENERAL_UPDATED,
            SIGNAL_DEVICE_RENDERING_CONTROL_UPDATED,
        ):
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    signal.format(self._device.udn),
                    self._async_handle_device_update,
                )
            )

    @callback
    def _async_handle_device_update(self, *_args: object) -> None:
        """Publish current output and availability from the SDK cache."""
        self._attr_options = [
            mode
            for mode in self._device.supported_output_modes
            if _normalize_output_mode(mode) != OTHER_OUTPUT
        ]
        current = _normalize_output_mode(self._device.output_mode)
        self._attr_current_option = current if current in self._attr_options else None
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Refresh available outputs and the active output."""
        self._attr_options = [
            mode
            for mode in self._device.supported_output_modes
            if _normalize_output_mode(mode) != OTHER_OUTPUT
        ]
        try:
            current = _normalize_output_mode(
                await self._device.get_audio_output_hw_mode()
            )
        except (WiimException, UpnpError, aiohttp.ClientError, TimeoutError) as err:
            LOGGER.debug(
                "Unable to read audio output for %s: %s", self._device.name, err
            )
            return
        self._attr_current_option = current if current in self._attr_options else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Switch the device to the selected audio output."""
        try:
            await self._device.async_set_output_mode(option)
        except (WiimException, UpnpError, aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "async_set_output_mode",
                    "entity_id": self.entity_id or self._device.name,
                },
            ) from err
        self._attr_current_option = option
        self.async_write_ha_state()
