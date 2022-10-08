"""Platform for switch integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from boschshcpy import (
    SHCCamera360,
    SHCCameraEyes,
    SHCLightSwitch,
    SHCSession,
    SHCSmartPlug,
    SHCSmartPlugCompact,
)
from boschshcpy.device import SHCDevice

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity


@dataclass
class SHCSwitchRequiredKeysMixin:
    """Mixin for SHC switch required keys."""

    on_key: str
    on_value: StateType
    should_poll: bool


@dataclass
class SHCSwitchEntityDescription(
    SwitchEntityDescription,
    SHCSwitchRequiredKeysMixin,
):
    """Class describing SHC switch entities."""


SWITCH_TYPES: dict[str, SHCSwitchEntityDescription] = {
    "smartplug": SHCSwitchEntityDescription(
        key="smartplug",
        device_class=SwitchDeviceClass.OUTLET,
        on_key="state",
        on_value=SHCSmartPlug.PowerSwitchService.State.ON,
        should_poll=False,
    ),
    "smartplugcompact": SHCSwitchEntityDescription(
        key="smartplugcompact",
        device_class=SwitchDeviceClass.OUTLET,
        on_key="state",
        on_value=SHCSmartPlugCompact.PowerSwitchService.State.ON,
        should_poll=False,
    ),
    "lightswitch": SHCSwitchEntityDescription(
        key="lightswitch",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="state",
        on_value=SHCLightSwitch.PowerSwitchService.State.ON,
        should_poll=False,
    ),
    "cameraeyes": SHCSwitchEntityDescription(
        key="cameraeyes",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="cameralight",
        on_value=SHCCameraEyes.CameraLightService.State.ON,
        should_poll=True,
    ),
    "camera360": SHCSwitchEntityDescription(
        key="camera360",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="privacymode",
        on_value=SHCCamera360.PrivacyModeService.State.DISABLED,
        should_poll=True,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SHC switch platform."""
    entities: list[SwitchEntity] = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for switch in session.device_helper.smart_plugs:

        entities.append(
            SHCSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["smartplug"],
            )
        )
        entities.append(
            SHCRoutingSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    for switch in session.device_helper.light_switches:

        entities.append(
            SHCSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["lightswitch"],
            )
        )

    for switch in session.device_helper.smart_plugs_compact:

        entities.append(
            SHCSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["smartplugcompact"],
            )
        )

    for switch in session.device_helper.camera_eyes:

        entities.append(
            SHCSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["cameraeyes"],
            )
        )

    for switch in session.device_helper.camera_360:

        entities.append(
            SHCSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["camera360"],
            )
        )

    if entities:
        async_add_entities(entities)


class SHCSwitch(SHCEntity, SwitchEntity):
    """Representation of a SHC switch."""

    entity_description: SHCSwitchEntityDescription

    def __init__(
        self,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
        description: SHCSwitchEntityDescription,
    ) -> None:
        """Initialize a SHC switch."""
        super().__init__(device, parent_id, entry_id)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return (
            getattr(self._device, self.entity_description.on_key)
            == self.entity_description.on_value
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        setattr(self._device, self.entity_description.on_key, True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        setattr(self._device, self.entity_description.on_key, False)

    @property
    def should_poll(self) -> bool:
        """Switch needs polling."""
        return self.entity_description.should_poll

    def update(self) -> None:
        """Trigger an update of the device."""
        self._device.update()


class SHCRoutingSwitch(SHCEntity, SwitchEntity):
    """Representation of a SHC routing switch."""

    _attr_icon = "mdi:wifi"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: SHCDevice, parent_id: str, entry_id: str) -> None:
        """Initialize an SHC communication quality reporting sensor."""
        super().__init__(device, parent_id, entry_id)
        self._attr_name = f"{device.name} Routing"
        self._attr_unique_id = f"{device.serial}_routing"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self._device.routing.name == "ENABLED"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._device.routing = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._device.routing = False
