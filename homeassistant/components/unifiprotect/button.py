"""Support for Ubiquiti's UniFi Protect NVR."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

from pyunifiprotect.data import ProtectAdoptableDeviceModel, ProtectModelWithId

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICES_THAT_ADOPT, DISPATCH_ADD, DISPATCH_ADOPT, DOMAIN
from .data import ProtectData
from .entity import ProtectDeviceEntity, async_all_device_entities
from .models import PermRequired, ProtectSetableKeysMixin, T
from .utils import async_dispatch_id as _ufpd

_LOGGER = logging.getLogger(__name__)


@dataclass
class ProtectButtonEntityDescription(
    ProtectSetableKeysMixin[T], ButtonEntityDescription
):
    """Describes UniFi Protect Button entity."""

    ufp_press: str | None = None


DEVICE_CLASS_CHIME_BUTTON: Final = "unifiprotect__chime_button"
KEY_ADOPT = "adopt"


ALL_DEVICE_BUTTONS: tuple[ProtectButtonEntityDescription, ...] = (
    ProtectButtonEntityDescription(
        key="reboot",
        entity_registry_enabled_default=False,
        device_class=ButtonDeviceClass.RESTART,
        name="Reboot Device",
        ufp_press="reboot",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectButtonEntityDescription(
        key="unadopt",
        entity_registry_enabled_default=False,
        name="Unadopt Device",
        icon="mdi:delete",
        ufp_press="unadopt",
        ufp_perm=PermRequired.DELETE,
    ),
)

ADOPT_BUTTON = ProtectButtonEntityDescription[ProtectAdoptableDeviceModel](
    key=KEY_ADOPT,
    name="Adopt Device",
    icon="mdi:plus-circle",
    ufp_press="adopt",
)

SENSOR_BUTTONS: tuple[ProtectButtonEntityDescription, ...] = (
    ProtectButtonEntityDescription(
        key="clear_tamper",
        name="Clear Tamper",
        icon="mdi:notification-clear-all",
        ufp_press="clear_tamper",
        ufp_perm=PermRequired.WRITE,
    ),
)

CHIME_BUTTONS: tuple[ProtectButtonEntityDescription, ...] = (
    ProtectButtonEntityDescription(
        key="play",
        name="Play Chime",
        device_class=DEVICE_CLASS_CHIME_BUTTON,
        icon="mdi:play",
        ufp_press="play",
    ),
    ProtectButtonEntityDescription(
        key="play_buzzer",
        name="Play Buzzer",
        icon="mdi:play",
        ufp_press="play_buzzer",
    ),
)


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
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover devices on a UniFi Protect NVR."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]

    async def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        entities = async_all_device_entities(
            data,
            ProtectButton,
            all_descs=ALL_DEVICE_BUTTONS,
            unadopted_descs=[ADOPT_BUTTON],
            chime_descs=CHIME_BUTTONS,
            sense_descs=SENSOR_BUTTONS,
            ufp_device=device,
        )
        async_add_entities(entities)
        _async_remove_adopt_button(hass, device)

    @callback
    def _async_add_unadopted_device(device: ProtectAdoptableDeviceModel) -> None:
        if not device.can_adopt or not device.can_create(data.api.bootstrap.auth_user):
            _LOGGER.debug("Device is not adoptable: %s", device.id)
            return

        entities = async_all_device_entities(
            data,
            ProtectButton,
            unadopted_descs=[ADOPT_BUTTON],
            ufp_device=device,
        )
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(hass, _ufpd(entry, DISPATCH_ADOPT), _add_new_device)
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, _ufpd(entry, DISPATCH_ADD), _async_add_unadopted_device
        )
    )

    entities: list[ProtectDeviceEntity] = async_all_device_entities(
        data,
        ProtectButton,
        all_descs=ALL_DEVICE_BUTTONS,
        unadopted_descs=[ADOPT_BUTTON],
        chime_descs=CHIME_BUTTONS,
        sense_descs=SENSOR_BUTTONS,
    )
    async_add_entities(entities)

    for device in data.get_by_types(DEVICES_THAT_ADOPT):
        _async_remove_adopt_button(hass, device)


class ProtectButton(ProtectDeviceEntity, ButtonEntity):
    """A Ubiquiti UniFi Protect Reboot button."""

    entity_description: ProtectButtonEntityDescription

    def __init__(
        self,
        data: ProtectData,
        device: ProtectAdoptableDeviceModel,
        description: ProtectButtonEntityDescription,
    ) -> None:
        """Initialize an UniFi camera."""
        super().__init__(data, device, description)
        self._attr_name = f"{self.device.display_name} {self.entity_description.name}"

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)

        if self.entity_description.key == KEY_ADOPT:
            self._attr_available = self.device.can_adopt and self.device.can_create(
                self.data.api.bootstrap.auth_user
            )

    async def async_press(self) -> None:
        """Press the button."""

        if self.entity_description.ufp_press is not None:
            await getattr(self.device, self.entity_description.ufp_press)()
