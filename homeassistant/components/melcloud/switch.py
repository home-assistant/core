"""Support for MelCloud device switches."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pymelcloud import DEVICE_TYPE_ATW
from pymelcloud.device import PROPERTY_POWER

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, MelCloudDevice


@dataclass(frozen=True, kw_only=True)
class MelcloudSwitchEntityDescription(SwitchEntityDescription):
    """Describes Melnor switch entity."""

    on_off_fn: Callable[[MelCloudDevice, bool], Coroutine[Any, Any, None]]
    state_fn: Callable[[MelCloudDevice], Any]


ATW_SWITCHES: tuple[MelcloudSwitchEntityDescription, ...] = (
    MelcloudSwitchEntityDescription(
        key="power",
        translation_key="power",
        device_class=SwitchDeviceClass.SWITCH,
        on_off_fn=lambda x, bool: x.device.set({PROPERTY_POWER: bool}),
        state_fn=lambda x: x.device.power or False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up MelCloud device climate based on config_entry."""
    mel_devices = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MelcloudSwitch(mel_device, description)
            for description in ATW_SWITCHES
            for mel_device in mel_devices[DEVICE_TYPE_ATW]
        ],
        True,
    )


class MelcloudSwitch(SwitchEntity):
    """Set up MELCloud device switches based on config_entry."""

    entity_description: MelcloudSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self, api: MelCloudDevice, description: MelcloudSwitchEntityDescription
    ) -> None:
        """Initialize a switch for a melcloud device."""
        self._api = api
        self.entity_description = description
        self._attr_unique_id = f"{api.device.serial}-{api.device.mac}-{description.key}"
        self._attr_device_info = api.device_info

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.entity_description.state_fn(self._api)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.entity_description.on_off_fn(self._api, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.entity_description.on_off_fn(self._api, False)
        self.async_write_ha_state()
