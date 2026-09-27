"""Platform for switch integration."""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, override

from boschshcpy import (
    BypassService,
    CameraLightService,
    PowerSwitchService,
    PrivacyModeService,
    SHCShutterContact2,
    SHCShutterContact2Plus,
    SHCSmartPlug,
    SilentModeService,
    ThermostatService,
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

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SHCSwitchEntityDescription(SwitchEntityDescription):
    """Class describing SHC switch entities."""

    on_key: str
    on_value: bool | Enum
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
    "child_lock": SHCSwitchEntityDescription(
        key="child_lock",
        translation_key="child_lock",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="child_lock",
        on_value=True,
        should_poll=False,
    ),
    "child_lock_thermostat": SHCSwitchEntityDescription(
        key="child_lock_thermostat",
        translation_key="child_lock",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="child_lock",
        on_value=ThermostatService.State.ON,
        should_poll=False,
    ),
    "presencesimulation": SHCSwitchEntityDescription(
        key="presencesimulation",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="enabled",
        on_value=True,
        should_poll=False,
    ),
    "bypass": SHCSwitchEntityDescription(
        key="bypass",
        translation_key="bypass",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="bypass",
        on_value=BypassService.State.BYPASS_ACTIVE,
        should_poll=False,
    ),
    "energy_saving_mode_enabled": SHCSwitchEntityDescription(
        key="energy_saving_mode_enabled",
        translation_key="energy_saving_mode_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="energy_saving_mode_enabled",
        on_value=True,
        should_poll=False,
    ),
    "humidity_warning_enabled": SHCSwitchEntityDescription(
        key="humidity_warning_enabled",
        translation_key="humidity_warning_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="humidity_warning_enabled",
        on_value=True,
        should_poll=False,
    ),
    "intrusion_alarm": SHCSwitchEntityDescription(
        key="intrusion_alarm",
        translation_key="intrusion_alarm",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="intrusion_alarm",
        on_value=True,
        should_poll=False,
    ),
    "nightly_promise_enabled": SHCSwitchEntityDescription(
        key="nightly_promise_enabled",
        translation_key="nightly_promise_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="nightly_promise_enabled",
        on_value=True,
        should_poll=False,
    ),
    "pet_immunity_enabled": SHCSwitchEntityDescription(
        key="pet_immunity_enabled",
        translation_key="pet_immunity_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="pet_immunity_enabled",
        on_value=True,
        should_poll=False,
    ),
    "tamper_protection_enabled": SHCSwitchEntityDescription(
        key="tamper_protection_enabled",
        translation_key="tamper_protection_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="tamper_protection_enabled",
        on_value=True,
        should_poll=False,
    ),
    "silent_mode": SHCSwitchEntityDescription(
        key="silent_mode",
        translation_key="silent_mode",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="silentmode",
        on_value=SilentModeService.State.MODE_SILENT,
        should_poll=False,
    ),
    "smart_sensitivity_enabled": SHCSwitchEntityDescription(
        key="smart_sensitivity_enabled",
        translation_key="smart_sensitivity_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="smart_sensitivity_enabled",
        on_value=True,
        should_poll=False,
    ),
    "vibration_enabled": SHCSwitchEntityDescription(
        key="vibration_enabled",
        translation_key="vibration_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="enabled",
        on_value=True,
        should_poll=False,
    ),
    "swap_inputs": SHCSwitchEntityDescription(
        key="swap_inputs",
        translation_key="swap_inputs",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="swap_inputs",
        on_value=True,
        should_poll=False,
    ),
    "swap_outputs": SHCSwitchEntityDescription(
        key="swap_outputs",
        translation_key="swap_outputs",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        on_key="swap_outputs",
        on_value=True,
        should_poll=False,
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
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["smartplug"],
        )
        for switch in session.device_helper.smart_plugs
    ]

    entities.extend(
        SHCRoutingSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for switch in session.device_helper.smart_plugs
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["lightswitch"],
        )
        for switch in session.device_helper.light_switches_bsm
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["smartplugcompact"],
        )
        for switch in session.device_helper.smart_plugs_compact
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["cameraeyes"],
        )
        for switch in session.device_helper.camera_eyes
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["camera360"],
        )
        for switch in session.device_helper.camera_360
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["child_lock_thermostat"],
            unique_id_suffix="child_lock",
        )
        for switch in (
            *session.device_helper.thermostats,
            *session.device_helper.roomthermostats,
            *session.device_helper.wallthermostats,
        )
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["child_lock"],
            unique_id_suffix="child_lock",
        )
        for switch in (
            *session.device_helper.micromodule_shutter_controls,
            *session.device_helper.micromodule_blinds,
            *session.device_helper.micromodule_light_attached,
            *session.device_helper.micromodule_relays,
            *session.device_helper.micromodule_impulse_relays,
            *session.device_helper.micromodule_dimmers,
            *session.device_helper.light_switches_bsm,
        )
    )

    presence_simulation_system = session.device_helper.presence_simulation_system
    if presence_simulation_system is not None:
        entities.append(
            SHCSwitch(
                hass=hass,
                device=presence_simulation_system,
                parent_id=shc_info.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["presencesimulation"],
            )
        )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["bypass"],
        )
        for switch in session.device_helper.shutter_contacts2
    )

    entities.extend(
        SHCBypassInfiniteSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for switch in session.device_helper.shutter_contacts2
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["vibration_enabled"],
            unique_id_suffix="vibration_enabled",
        )
        for switch in session.device_helper.shutter_contacts2
        if isinstance(switch, SHCShutterContact2Plus)
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["pet_immunity_enabled"],
            unique_id_suffix="pet_immunity",
        )
        for switch in session.device_helper.motion_detectors2
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["tamper_protection_enabled"],
            unique_id_suffix="tamper_protection",
        )
        for switch in session.device_helper.motion_detectors2
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["intrusion_alarm"],
        )
        for switch in session.device_helper.smoke_detectors
        if switch.supports_intrusion_alarm
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["silent_mode"],
            unique_id_suffix="silent_mode",
        )
        for switch in session.device_helper.thermostats
        if switch.supports_silentmode
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["nightly_promise_enabled"],
        )
        for switch in session.device_helper.twinguards
        if switch.supports_nightly_promise
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["energy_saving_mode_enabled"],
            unique_id_suffix="energy_saving_mode",
        )
        for switch in session.device_helper.smart_plugs
        if switch.supports_energy_saving_mode
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["energy_saving_mode_enabled"],
            unique_id_suffix="energy_saving_mode",
        )
        for switch in session.device_helper.smart_plugs_compact
        if switch.supports_energy_saving_mode
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["humidity_warning_enabled"],
        )
        for switch in (
            *session.device_helper.thermostats,
            *session.device_helper.roomthermostats,
        )
        if getattr(switch, "supports_display_configuration", False)
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["smart_sensitivity_enabled"],
            unique_id_suffix="smart_sensitivity",
        )
        for switch in session.device_helper.motion_detectors2
        if switch.supports_smart_sensitivity
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["swap_inputs"],
            unique_id_suffix="swap_inputs",
        )
        for switch in session.device_helper.micromodule_relays
        if getattr(switch, "supports_switch_configuration", False)
        and getattr(switch, "swap_inputs", None) is not None
    )

    entities.extend(
        SHCSwitch(
            hass=hass,
            device=switch,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["swap_outputs"],
            unique_id_suffix="swap_outputs",
        )
        for switch in session.device_helper.micromodule_relays
        if getattr(switch, "supports_switch_configuration", False)
        and getattr(switch, "swap_outputs", None) is not None
    )

    async_add_entities(entities)


class SHCSwitch(SHCEntity, SwitchEntity):
    """Representation of a SHC switch."""

    entity_description: SHCSwitchEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
        description: SHCSwitchEntityDescription,
        unique_id_suffix: str | None = None,
    ) -> None:
        """Initialize a SHC switch."""
        super().__init__(hass, device, parent_id, entry_id)
        self.entity_description = description
        if unique_id_suffix is not None:
            self._attr_unique_id = f"{device.serial}_{unique_id_suffix}"

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

    def __init__(
        self, hass: HomeAssistant, device: SHCDevice, parent_id: str, entry_id: str
    ) -> None:
        """Initialize an SHC routing switch."""
        super().__init__(hass, device, parent_id, entry_id)
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


class SHCBypassInfiniteSwitch(SHCEntity, SwitchEntity):
    """Representation of a SHC alarm-bypass "never expires" switch."""

    _attr_translation_key = "bypass_infinite"
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG
    _device: SHCShutterContact2

    def __init__(
        self, hass: HomeAssistant, device: SHCDevice, parent_id: str, entry_id: str
    ) -> None:
        """Initialize an SHC bypass-never-expires switch."""
        super().__init__(hass, device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_bypass_infinite"

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self._device.bypass_infinite

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._device.set_bypass_configuration(infinite=True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._device.set_bypass_configuration(infinite=False)
