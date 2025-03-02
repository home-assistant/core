"""Support for Ubiquiti's UniFi Protect NVR."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
import logging
from typing import TYPE_CHECKING, Final

from uiprotect.data import ModelType, ProtectAdoptableDeviceModel

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEVICES_THAT_ADOPT, DOMAIN
from .data import ProtectDeviceType, UFPConfigEntry
from .entity import (
    PermRequired,
    ProtectDeviceEntity,
    ProtectEntityDescription,
    ProtectSetableKeysMixin,
    T,
    async_all_device_entities,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ProtectButtonEntityDescription(
    ProtectSetableKeysMixin[T], ButtonEntityDescription
):
    """Describes UniFi Protect Button entity."""

    ufp_press: str | None = None


DEVICE_CLASS_CHIME_BUTTON: Final = "unifiprotect__chime_button"


ALL_DEVICE_BUTTONS: tuple[ProtectButtonEntityDescription, ...] = (
    ProtectButtonEntityDescription(
        key="reboot",
        entity_registry_enabled_default=False,
        device_class=ButtonDeviceClass.RESTART,
        name="Reboot device",
        ufp_press="reboot",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectButtonEntityDescription(
        key="unadopt",
        entity_registry_enabled_default=False,
        name="Unadopt device",
        icon="mdi:delete",
        ufp_press="unadopt",
        ufp_perm=PermRequired.DELETE,
    ),
)

ADOPT_BUTTON = ProtectButtonEntityDescription[ProtectAdoptableDeviceModel](
    key="adopt",
    name="Adopt device",
    icon="mdi:plus-circle",
    ufp_press="adopt",
)

SENSOR_BUTTONS: tuple[ProtectButtonEntityDescription, ...] = (
    ProtectButtonEntityDescription(
        key="clear_tamper",
        name="Clear tamper",
        icon="mdi:notification-clear-all",
        ufp_press="clear_tamper",
        ufp_perm=PermRequired.WRITE,
    ),
)

CHIME_BUTTONS: tuple[ProtectButtonEntityDescription, ...] = (
    ProtectButtonEntityDescription(
        key="play",
        name="Play chime",
        device_class=DEVICE_CLASS_CHIME_BUTTON,
        icon="mdi:play",
        ufp_press="play",
    ),
    ProtectButtonEntityDescription(
        key="play_buzzer",
        name="Play buzzer",
        icon="mdi:play",
        ufp_press="play_buzzer",
    ),
)


_MODEL_DESCRIPTIONS: dict[ModelType, Sequence[ProtectEntityDescription]] = {
    ModelType.CHIME: CHIME_BUTTONS,
    ModelType.SENSOR: SENSOR_BUTTONS,
}


@callback
def _async_remove_adopt_button(
    hass: HomeAssistant, device: ProtectAdoptableDeviceModel
) -> None:
    entity_registry = er.async_get(hass)
    if entity_id := entity_registry.async_get_entity_id(
        Platform.BUTTON, DOMAIN, f"{device.mac}_adopt"
    ):
        entity_registry.async_remove(entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Discover devices on a UniFi Protect NVR."""
    data = entry.runtime_data

    adopt_entities = partial(
        async_all_device_entities,
        data,
        ProtectAdoptButton,
        unadopted_descs=[ADOPT_BUTTON],
    )
    base_entities = partial(
        async_all_device_entities,
        data,
        ProtectButton,
        all_descs=ALL_DEVICE_BUTTONS,
        model_descriptions=_MODEL_DESCRIPTIONS,
    )

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        async_add_entities(
            [*base_entities(ufp_device=device), *adopt_entities(ufp_device=device)]
        )
        _async_remove_adopt_button(hass, device)

    @callback
    def _async_add_unadopted_device(device: ProtectAdoptableDeviceModel) -> None:
        if not device.can_adopt or not device.can_create(data.api.bootstrap.auth_user):
            _LOGGER.debug("Device is not adoptable: %s", device.id)
            return
        async_add_entities(adopt_entities(ufp_device=device))

    data.async_subscribe_adopt(_add_new_device)
    entry.async_on_unload(
        async_dispatcher_connect(hass, data.add_signal, _async_add_unadopted_device)
    )
    async_add_entities([*base_entities(), *adopt_entities()])

    for device in data.get_by_types(DEVICES_THAT_ADOPT):
        _async_remove_adopt_button(hass, device)


class ProtectButton(ProtectDeviceEntity, ButtonEntity):
    """A Ubiquiti UniFi Protect Reboot button."""

    entity_description: ProtectButtonEntityDescription

    async def async_press(self) -> None:
        """Press the button."""
        if self.entity_description.ufp_press is not None:
            await getattr(self.device, self.entity_description.ufp_press)()


class ProtectAdoptButton(ProtectButton):
    """A Ubiquiti UniFi Protect Adopt button."""

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        if TYPE_CHECKING:
            assert isinstance(device, ProtectAdoptableDeviceModel)
        self._attr_available = device.can_adopt and device.can_create(
            self.data.api.bootstrap.auth_user
        )
