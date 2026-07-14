"""Platform for switch integration."""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, override

from boschshcpy import (
    CameraLightService,
    PowerSwitchService,
    PrivacyModeService,
    SHCSmartPlug,
)
from boschshcpy.device import SHCDevice

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity


@dataclass(frozen=True, kw_only=True)
class SHCSwitchEntityDescription(SwitchEntityDescription):
    """Class describing SHC switch entities."""

    on_key: str
    on_value: Enum
    should_poll: bool


SWITCH_TYPES: dict[str, SHCSwitchEntityDescription] = {
    "smartplug": SHCSwitchEntityDescription(
        key="smartplug",
        device_class=SwitchDeviceClass.OUTLET,
        on_key="switchstate",
        on_value=PowerSwitchService.State.ON,
        should_poll=False,
    ),
    "smartplugcompact": SHCSwitchEntityDescription(
        key="smartplugcompact",
        device_class=SwitchDeviceClass.OUTLET,
        on_key="switchstate",
        on_value=PowerSwitchService.State.ON,
        should_poll=False,
    ),
    "lightswitch": SHCSwitchEntityDescription(
        key="lightswitch",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="switchstate",
        on_value=PowerSwitchService.State.ON,
        should_poll=False,
    ),
    "cameraeyes": SHCSwitchEntityDescription(
        key="cameraeyes",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="cameralight",
        on_value=CameraLightService.State.ON,
        should_poll=True,
    ),
    "camera360": SHCSwitchEntityDescription(
        key="camera360",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="privacymode",
        on_value=PrivacyModeService.State.DISABLED,
        should_poll=True,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC switch platform."""
    session = config_entry.runtime_data

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    entities: list[SwitchEntity] = [
        SHCSwitch(
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["smartplug"],
        )
        for switch in session.device_helper.smart_plugs
    ]

    entities.extend(
        SHCRoutingSwitch(
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for switch in session.device_helper.smart_plugs
    )

    entities.extend(
        SHCSwitch(
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["lightswitch"],
        )
        for switch in session.device_helper.light_switches_bsm
    )

    entities.extend(
        SHCSwitch(
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["smartplugcompact"],
        )
        for switch in session.device_helper.smart_plugs_compact
    )

    entities.extend(
        SHCSwitch(
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["cameraeyes"],
        )
        for switch in session.device_helper.camera_eyes
    )

    entities.extend(
        SHCSwitch(
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["camera360"],
        )
        for switch in session.device_helper.camera_360
    )

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
    @override
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return (
            getattr(self._device, self.entity_description.on_key)
            is self.entity_description.on_value
        )

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        setattr(self._device, self.entity_description.on_key, True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        setattr(self._device, self.entity_description.on_key, False)

    @property
    @override
    def should_poll(self) -> bool:
        """Switch needs polling."""
        return self.entity_description.should_poll

    def update(self) -> None:
        """Trigger an update of the device."""
        self._device.update()


class SHCRoutingSwitch(SHCEntity, SwitchEntity):
    """Representation of a SHC routing switch."""

    _attr_translation_key = "routing"
    _attr_entity_category = EntityCategory.CONFIG
    _device: SHCSmartPlug

    def __init__(self, device: SHCDevice, parent_id: str, entry_id: str) -> None:
        """Initialize an SHC routing switch."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_routing"

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self._device.routing.name == "ENABLED"

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._device.routing = True

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._device.routing = False
