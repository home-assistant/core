"""Switches for AVM Fritz!Box buttons."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BUTTON_TYPE_WOL, CONNECTION_TYPE_LAN, DOMAIN, MeshRoles
from .coordinator import FRITZ_DATA_KEY, AvmWrapper, FritzConfigEntry, FritzData
from .entity import FritzDeviceBase
from .helpers import _is_tracked
from .models import FritzDevice

_LOGGER = logging.getLogger(__name__)

# Set a sane value to avoid too many updates
PARALLEL_UPDATES = 5


@dataclass(frozen=True, kw_only=True)
class FritzButtonDescription(ButtonEntityDescription):
    """Class to describe a Button entity."""

    press_action: Callable[[AvmWrapper], Any]


BUTTONS: Final = [
    FritzButtonDescription(
        key="firmware_update",
        translation_key="firmware_update",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda avm_wrapper: avm_wrapper.async_trigger_firmware_update(),
        entity_registry_enabled_default=False,
    ),
    FritzButtonDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda avm_wrapper: avm_wrapper.async_trigger_reboot(),
    ),
    FritzButtonDescription(
        key="reconnect",
        translation_key="reconnect",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda avm_wrapper: avm_wrapper.async_trigger_reconnect(),
    ),
    FritzButtonDescription(
        key="cleanup",
        translation_key="cleanup",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda avm_wrapper: avm_wrapper.async_trigger_cleanup(),
        entity_registry_enabled_default=False,
    ),
]


def repair_issue_cleanup(hass: HomeAssistant, avm_wrapper: AvmWrapper) -> None:
    """Repair issue for cleanup button."""
    entity_registry = er.async_get(hass)

    if (
        (
            entity_button := entity_registry.async_get_entity_id(
                "button", DOMAIN, f"{avm_wrapper.unique_id}-cleanup"
            )
        )
        and (entity_entry := entity_registry.async_get(entity_button))
        and not entity_entry.disabled
    ):
        # Deprecate the 'cleanup' button: create a Repairs issue for users
        ir.async_create_issue(
            hass,
            domain=DOMAIN,
            issue_id="deprecated_cleanup_button",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_cleanup_button",
            translation_placeholders={"removal_version": "2026.11.0"},
            breaks_in_ha_version="2026.11.0",
        )


def repair_issue_firmware_update(hass: HomeAssistant, avm_wrapper: AvmWrapper) -> None:
    """Repair issue for firmware update button."""
    entity_registry = er.async_get(hass)

    if (
        (
            entity_button := entity_registry.async_get_entity_id(
                "button", DOMAIN, f"{avm_wrapper.unique_id}-firmware_update"
            )
        )
        and (entity_entry := entity_registry.async_get(entity_button))
        and not entity_entry.disabled
    ):
        # Deprecate the 'firmware update' button: create a Repairs issue for users
        ir.async_create_issue(
            hass,
            domain=DOMAIN,
            issue_id="deprecated_firmware_update_button",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_firmware_update_button",
            translation_placeholders={"removal_version": "2026.11.0"},
            breaks_in_ha_version="2026.11.0",
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set buttons for device."""
    _LOGGER.debug("Setting up buttons")
    avm_wrapper = entry.runtime_data

    entities_list: list[ButtonEntity] = [
        FritzButton(avm_wrapper, entry.title, button) for button in BUTTONS
    ]

    if avm_wrapper.mesh_role == MeshRoles.SLAVE:
        async_add_entities(entities_list)
        repair_issue_cleanup(hass, avm_wrapper)
        repair_issue_firmware_update(hass, avm_wrapper)
        return

    data_fritz = hass.data[FRITZ_DATA_KEY]
    entities_list += _async_wol_buttons_list(avm_wrapper, data_fritz)

    async_add_entities(entities_list)

    @callback
    def async_update_avm_device() -> None:
        """Update the values of the AVM device."""
        async_add_entities(_async_wol_buttons_list(avm_wrapper, data_fritz))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, avm_wrapper.signal_device_new, async_update_avm_device
        )
    )

    repair_issue_cleanup(hass, avm_wrapper)
    repair_issue_firmware_update(hass, avm_wrapper)


class FritzButton(ButtonEntity):
    """Defines a Fritz!Box base button."""

    entity_description: FritzButtonDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        description: FritzButtonDescription,
    ) -> None:
        """Initialize Fritz!Box button."""
        self.entity_description = description
        self.avm_wrapper = avm_wrapper

        self._attr_unique_id = f"{self.avm_wrapper.unique_id}-{description.key}"

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, avm_wrapper.mac)},
            name=device_friendly_name,
        )

    async def async_press(self) -> None:
        """Triggers Fritz!Box service."""
        if self.entity_description.key == "cleanup":
            _LOGGER.warning(
                "The 'cleanup' button is deprecated and will be removed in Home Assistant Core 2026.11.0. "
                "Please update your automations and dashboards to remove any usage of this button. "
                "The action is now performed automatically at each data refresh",
            )
        elif self.entity_description.key == "firmware_update":
            _LOGGER.warning(
                "The 'firmware update' button is deprecated and will be removed in Home Assistant Core "
                "2026.11.0. It has been superseded by an update entity. Please update your automations "
                "and dashboards to remove any usage of this button",
            )
        await self.entity_description.press_action(self.avm_wrapper)


@callback
def _async_wol_buttons_list(
    avm_wrapper: AvmWrapper,
    data_fritz: FritzData,
) -> list[FritzBoxWOLButton]:
    """Add new WOL button entities from the AVM device."""
    _LOGGER.debug("Setting up %s buttons", BUTTON_TYPE_WOL)

    new_wols: list[FritzBoxWOLButton] = []

    if avm_wrapper.unique_id not in data_fritz.wol_buttons:
        data_fritz.wol_buttons[avm_wrapper.unique_id] = set()

    for mac, device in avm_wrapper.devices.items():
        if _is_tracked(mac, data_fritz.wol_buttons.values()):
            _LOGGER.debug("Skipping wol button creation for device %s", device.hostname)
            continue

        if device.connection_type != CONNECTION_TYPE_LAN:
            _LOGGER.debug(
                "Skipping wol button creation for device %s, not connected via LAN",
                device.hostname,
            )
            continue

        new_wols.append(FritzBoxWOLButton(avm_wrapper, device))
        data_fritz.wol_buttons[avm_wrapper.unique_id].add(mac)

    _LOGGER.debug("Creating %s wol buttons", len(new_wols))
    return new_wols


class FritzBoxWOLButton(FritzDeviceBase, ButtonEntity):
    """Defines a FRITZ!Box Tools Wake On LAN button."""

    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "wake_on_lan"

    def __init__(self, avm_wrapper: AvmWrapper, device: FritzDevice) -> None:
        """Initialize Fritz!Box WOL button."""
        super().__init__(avm_wrapper, device)
        self._attr_unique_id = f"{self._mac}_wake_on_lan"
        self._is_available = True

    async def async_press(self) -> None:
        """Press the button."""
        if self.mac_address:
            await self._avm_wrapper.async_wake_on_lan(self.mac_address)
