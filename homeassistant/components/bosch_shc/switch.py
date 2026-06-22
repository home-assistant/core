"""Platform for switch integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiohttp

from boschshcpy import (
    SHCCamera360,
    SHCCameraEyes,
    SHCCameraOutdoorGen2,
    SHCLightSwitch,
    SHCSession,
    SHCSmartPlug,
    SHCMicromoduleRelay,
    SHCSmartPlugCompact,
    SHCShutterContact2,
    SHCShutterContact2Plus,
    SHCThermostat,
    SHCUserDefinedState,
)
from boschshcpy.device import SHCDevice

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import slugify
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DATA_SESSION, DOMAIN, DATA_SHC
from .entity import SHCEntity, async_migrate_to_new_unique_id, device_excluded

LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass
class SHCSwitchRequiredKeysMixin:
    """Mixin for SHC switch required keys."""

    key: str
    on_key: str
    on_value: StateType
    should_poll: bool | False
    device_class: SwitchDeviceClass | None = None
    icon: str | None = None
    entity_category: EntityCategory | None = None


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
        on_key="switchstate",
        on_value=SHCSmartPlug.PowerSwitchService.State.ON,
        should_poll=False,
    ),
    "smartplug_routing": SHCSwitchEntityDescription(
        key="smartplug_routing",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="routing",
        on_value=SHCSmartPlug.RoutingService.State.ENABLED,
        should_poll=False,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:wifi",
    ),
    "smartplugcompact": SHCSwitchEntityDescription(
        key="smartplugcompact",
        device_class=SwitchDeviceClass.OUTLET,
        on_key="switchstate",
        on_value=SHCSmartPlugCompact.PowerSwitchService.State.ON,
        should_poll=False,
    ),
    "micromodule_relay_switch": SHCSwitchEntityDescription(
        key="micromodule_relay_switch",
        device_class=SwitchDeviceClass.OUTLET,
        on_key="switchstate",
        on_value=SHCMicromoduleRelay.PowerSwitchService.State.ON,
        should_poll=False,
    ),
    "lightswitch": SHCSwitchEntityDescription(
        key="lightswitch",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="switchstate",
        on_value=SHCLightSwitch.PowerSwitchService.State.ON,
        should_poll=False,
    ),
    "cameraeyes": SHCSwitchEntityDescription(
        key="cameraeyes",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="privacymode",
        on_value=SHCCameraEyes.PrivacyModeService.State.DISABLED,
        should_poll=True,
        icon="mdi:video",
    ),
    "cameraeyes_cameralight": SHCSwitchEntityDescription(
        key="cameraeyes_cameralight",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="cameralight",
        on_value=SHCCameraEyes.CameraLightService.State.ON,
        should_poll=True,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:light-flood-down",
    ),
    "cameraeyes_notification": SHCSwitchEntityDescription(
        key="cameraeyes_notification",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="cameranotification",
        on_value=SHCCameraEyes.CameraNotificationService.State.ENABLED,
        should_poll=True,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:message-badge",
    ),
    "camera360": SHCSwitchEntityDescription(
        key="camera360",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="privacymode",
        on_value=SHCCamera360.PrivacyModeService.State.DISABLED,
        should_poll=True,
        icon="mdi:video",
    ),
    "camera360_notification": SHCSwitchEntityDescription(
        key="camera360_notification",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="cameranotification",
        on_value=SHCCamera360.CameraNotificationService.State.ENABLED,
        should_poll=True,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:message-badge",
    ),
    "cameraoutdoorgen2": SHCSwitchEntityDescription(
        key="cameraoutdoorgen2",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="privacymode",
        on_value=SHCCameraOutdoorGen2.PrivacyModeService.State.DISABLED,
        should_poll=True,
        icon="mdi:video",
    ),
    "cameraoutdoorgen2_camerafrontlight": SHCSwitchEntityDescription(
        key="cameraoutdoorgen2_camerafrontlight",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="camerafrontlight",
        on_value=SHCCameraOutdoorGen2.CameraFrontLightService.State.ON,
        should_poll=True,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:light-flood-down",
    ),
    "cameraoutdoorgen2_cameraambientlight": SHCSwitchEntityDescription(
        key="cameraoutdoorgen2_cameraambientlight",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="cameraambientlight",
        on_value=SHCCameraOutdoorGen2.CameraAmbientLightService.State.ON,
        should_poll=True,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:wall-sconce-flat",
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
        device_class=SwitchDeviceClass.SWITCH,
        on_key="bypass",
        on_value=SHCShutterContact2.BypassService.State.BYPASS_ACTIVE,
        should_poll=False,
    ),
    "child_lock": SHCSwitchEntityDescription(
        key="child_lock",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="child_lock",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:lock",
    ),
    "child_lock_thermostat": SHCSwitchEntityDescription(
        key="child_lock_thermostat",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="child_lock",
        # Thermostats expose child lock as a ThermostatService.State enum, not a
        # bool. State.ON != True, so reusing the bool "child_lock" description
        # made the switch read OFF permanently. Compare against the enum member.
        on_value=SHCThermostat.ThermostatService.State.ON,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:lock",
    ),
    "pet_immunity_enabled": SHCSwitchEntityDescription(
        key="pet_immunity_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="pet_immunity_enabled",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:paw",
    ),
    "energy_saving_mode_enabled": SHCSwitchEntityDescription(
        key="energy_saving_mode_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="energy_saving_mode_enabled",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:leaf",
    ),
    "warning_suppressed": SHCSwitchEntityDescription(
        key="warning_suppressed",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="warning_suppressed",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:bell-off",
    ),
    "nightly_promise_enabled": SHCSwitchEntityDescription(
        key="nightly_promise_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="nightly_promise_enabled",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:shield-check",
    ),
    "humidity_warning_enabled": SHCSwitchEntityDescription(
        key="humidity_warning_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="humidity_warning_enabled",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:water-alert",
    ),
    "swap_inputs": SHCSwitchEntityDescription(
        key="swap_inputs",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="swap_inputs",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:swap-horizontal",
    ),
    "swap_outputs": SHCSwitchEntityDescription(
        key="swap_outputs",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="swap_outputs",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:swap-horizontal-bold",
    ),
    "pre_alarm_enabled": SHCSwitchEntityDescription(
        key="pre_alarm_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="pre_alarm_enabled",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:smoke-detector",
    ),
    "smart_sensitivity_enabled": SHCSwitchEntityDescription(
        key="smart_sensitivity_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="smart_sensitivity_enabled",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:tune",
    ),
    "tamper_protection_enabled": SHCSwitchEntityDescription(
        key="tamper_protection_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="tamper_protection_enabled",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:shield-lock",
    ),
    "silent_mode": SHCSwitchEntityDescription(
        key="silent_mode",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="silentmode",
        on_value=SHCThermostat.SilentModeService.State.MODE_SILENT,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
        icon="mdi:sleep",
    ),
    "vibration_enabled": SHCSwitchEntityDescription(
        key="vibration_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="enabled",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
    ),
    "user_defined_state": SHCSwitchEntityDescription(
        key="user_defined_state",
        device_class=SwitchDeviceClass.SWITCH,
        on_key="state",
        on_value=True,
        entity_category=EntityCategory.CONFIG,
        should_poll=False,
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
        if device_excluded(switch, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["smartplug"],
            )
        )
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch, attr_name="Routing"
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["smartplug_routing"],
                attr_name="Routing",
            )
        )
        if (
            getattr(switch, "supports_energy_saving_mode", False)
            and getattr(switch, "energy_saving_mode_enabled", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["energy_saving_mode_enabled"],
                    attr_name="EnergySavingMode",
                )
            )
        if (
            getattr(switch, "supports_power_switch_warning", False)
            and getattr(switch, "warning_suppressed", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["warning_suppressed"],
                    attr_name="WarningSuppressed",
                )
            )

    for switch in (
        session.device_helper.light_switches_bsm
        + session.device_helper.micromodule_light_attached
    ):
        if device_excluded(switch, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["lightswitch"],
            )
        )

    for switch in session.device_helper.smart_plugs_compact:
        if device_excluded(switch, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["smartplugcompact"],
            )
        )
        if (
            getattr(switch, "supports_energy_saving_mode", False)
            and getattr(switch, "energy_saving_mode_enabled", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["energy_saving_mode_enabled"],
                    attr_name="EnergySavingMode",
                )
            )
        if (
            getattr(switch, "supports_power_switch_warning", False)
            and getattr(switch, "warning_suppressed", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["warning_suppressed"],
                    attr_name="WarningSuppressed",
                )
            )

    for switch in session.device_helper.micromodule_relays:
        if device_excluded(switch, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["micromodule_relay_switch"],
            )
        )
        if (
            getattr(switch, "supports_switch_configuration", False)
            and getattr(switch, "swap_inputs", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["swap_inputs"],
                    attr_name="SwapInputs",
                )
            )
        if (
            getattr(switch, "supports_switch_configuration", False)
            and getattr(switch, "swap_outputs", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["swap_outputs"],
                    attr_name="SwapOutputs",
                )
            )

    for device in getattr(session.device_helper, "micromodule_light_controls", []):
        if device_excluded(device, config_entry.options):
            continue
        if (
            getattr(device, "supports_switch_configuration", False)
            and getattr(device, "swap_inputs", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=device,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["swap_inputs"],
                    attr_name="SwapInputs",
                )
            )
        if (
            getattr(device, "supports_switch_configuration", False)
            and getattr(device, "swap_outputs", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=device,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["swap_outputs"],
                    attr_name="SwapOutputs",
                )
            )

    for switch in session.device_helper.camera_eyes:
        if device_excluded(switch, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass=hass,
            platform=Platform.SWITCH,
            device=switch,
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["cameraeyes"],
            )
        )
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch, attr_name="Light"
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["cameraeyes_cameralight"],
                attr_name="Light",
            )
        )
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch, attr_name="Notification"
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["cameraeyes_notification"],
                attr_name="Notification",
            )
        )

    for switch in session.device_helper.camera_360:
        if device_excluded(switch, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["camera360"],
            )
        )
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch, attr_name="Notification"
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["camera360_notification"],
                attr_name="Notification",
            )
        )

    for switch in session.device_helper.camera_outdoor_gen2:
        if device_excluded(switch, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass=hass,
            platform=Platform.SWITCH,
            device=switch,
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["cameraoutdoorgen2"],
            )
        )
        # #289-safe migration: in 0.4.106-0.4.111 both Gen2 camera lights shared
        # attr_name="Light" (uid _light); the Frontlight/AmbientLight split left
        # the old migration pointing at a phantom _light and gave AmbientLight no
        # migration at all.  Map the old id (both historical formats) to the real
        # Frontlight uid; async_migrate skips if the target already exists, so
        # already-upgraded users are unaffected.
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch,
            attr_name="Frontlight", old_unique_id=f"{switch.serial}_light",
        )
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch,
            attr_name="Frontlight",
            old_unique_id=f"{switch.root_device_id}_{switch.id}_light",
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["cameraoutdoorgen2_camerafrontlight"],
                attr_name="Frontlight",
            )
        )
        # AmbientLight had no prior migration; the old single _light entity is
        # claimed by Frontlight above, so these no-op for upgraders but cover a
        # registry where only AmbientLight's id survived.
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch,
            attr_name="AmbientLight", old_unique_id=f"{switch.serial}_light",
        )
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch,
            attr_name="AmbientLight",
            old_unique_id=f"{switch.root_device_id}_{switch.id}_light",
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["cameraoutdoorgen2_cameraambientlight"],
                attr_name="AmbientLight",
            )
        )

    presence_simulation_system = session.device_helper.presence_simulation_system
    if presence_simulation_system and not device_excluded(
        presence_simulation_system, config_entry.options
    ):
        await async_migrate_to_new_unique_id(
            hass=hass,
            platform=Platform.SWITCH,
            device=presence_simulation_system,
        )
        entities.append(
            SHCSwitch(
                device=presence_simulation_system,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["presencesimulation"],
            )
        )

    for switch in session.device_helper.shutter_contacts2:
        if device_excluded(switch, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass=hass, platform=Platform.SWITCH, device=switch
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["bypass"],
            )
        )
        if isinstance(switch, SHCShutterContact2Plus):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["vibration_enabled"],
                    attr_name="VibrationEnabled",
                )
            )

    for switch in session.device_helper.thermostats:
        if device_excluded(switch, config_entry.options):
            continue
        if switch.supports_silentmode:
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["silent_mode"],
                    attr_name="SilentMode",
                )
            )

    # Thermostats / room thermostats / wall thermostats expose child lock as a
    # ThermostatService.State enum (ON/OFF) -> needs the enum-aware description.
    for switch in (
        session.device_helper.thermostats
        + session.device_helper.roomthermostats
        # wall thermostats expose child_lock only with boschshcpy >= 0.2.119;
        # hasattr guard so an older (pinned) lib does not raise on device.child_lock
        + [d for d in session.device_helper.wallthermostats if hasattr(d, "child_lock")]
    ):
        if device_excluded(switch, config_entry.options):
            continue
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["child_lock_thermostat"],
                attr_name="ChildLock",
            )
        )

    # ChildProtection devices expose child lock as a bool (childLockActive).
    # micromodule_dimmers and light_switches_bsm also carry the ChildProtection
    # service but were previously not wired -> no child-lock entity was created.
    for switch in (
        session.device_helper.micromodule_shutter_controls
        + session.device_helper.micromodule_blinds
        + session.device_helper.micromodule_light_attached
        + session.device_helper.micromodule_relays
        + session.device_helper.micromodule_impulse_relays
        + session.device_helper.micromodule_dimmers
        + session.device_helper.light_switches_bsm
    ):
        if device_excluded(switch, config_entry.options):
            continue
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["child_lock"],
                attr_name="ChildLock",
            )
        )

    for switch in session.device_helper.motion_detectors2:
        if device_excluded(switch, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass=hass,
            platform=Platform.SWITCH,
            device=switch,
            attr_name="PetImmunity",
        )
        entities.append(
            SHCSwitch(
                device=switch,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["pet_immunity_enabled"],
                attr_name="PetImmunity",
            )
        )
        if hasattr(switch, "smart_sensitivity_enabled"):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["smart_sensitivity_enabled"],
                    attr_name="SmartSensitivity",
                )
            )
        if hasattr(switch, "tamper_protection_enabled"):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["tamper_protection_enabled"],
                    attr_name="TamperProtection",
                )
            )

    for switch in getattr(session.device_helper, "twinguards", []):
        if device_excluded(switch, config_entry.options):
            continue
        if (
            getattr(switch, "supports_nightly_promise", False)
            and getattr(switch, "nightly_promise_enabled", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["nightly_promise_enabled"],
                    attr_name="NightlyPromise",
                )
            )
        if (
            getattr(switch, "supports_smoke_sensitivity", False)
            and getattr(switch, "pre_alarm_enabled", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["pre_alarm_enabled"],
                    attr_name="PreAlarm",
                )
            )

    for switch in getattr(session.device_helper, "smoke_detectors", []):
        if device_excluded(switch, config_entry.options):
            continue
        if (
            getattr(switch, "supports_smoke_sensitivity", False)
            and getattr(switch, "pre_alarm_enabled", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["pre_alarm_enabled"],
                    attr_name="PreAlarm",
                )
            )

    # ThermostatGen2 / RoomThermostat2: humidity warning toggle.
    # Guarded by hasattr so old lib (no display_config) doesn't create it.
    for switch in (
        session.device_helper.thermostats + session.device_helper.roomthermostats
    ):
        if device_excluded(switch, config_entry.options):
            continue
        if (
            getattr(switch, "supports_display_configuration", False)
            and getattr(switch, "humidity_warning_enabled", None) is not None
        ):
            entities.append(
                SHCSwitch(
                    device=switch,
                    entry_id=config_entry.entry_id,
                    description=SWITCH_TYPES["humidity_warning_enabled"],
                    attr_name="HumidityWarning",
                )
            )

    if entities:
        async_add_entities(entities)

    @callback
    def async_add_userdefinedstateswitch(
        device: SHCUserDefinedState,
    ) -> None:
        """Add User Defined State Switch."""
        entity = SHCUserDefinedStateSwitch(
            device=device,
            hass=hass,
            session=session,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPES["user_defined_state"],
        )
        async_add_entities([entity])

    # add all current items in session
    for switch in session.userdefinedstates:
        async_add_userdefinedstateswitch(device=switch)

    # Register listener for new user-defined state switches and ensure it is
    # torn down on config entry unload.  session.subscribe() returns None, so
    # we build the unsubscribe closure ourselves.  add_update_listener expects
    # an options-update callback (hass, entry) -> None and must NOT be used here.
    _uds_subscriber = (SHCUserDefinedState, async_add_userdefinedstateswitch)
    session.subscribe(_uds_subscriber)

    def _unsubscribe_uds():
        try:
            session._subscribers.remove(_uds_subscriber)
        except ValueError:
            pass

    config_entry.async_on_unload(_unsubscribe_uds)


class SHCSwitch(SHCEntity, SwitchEntity):
    """Representation of a SHC switch."""

    entity_description: SHCSwitchEntityDescription

    def __init__(
        self,
        device: SHCDevice,
        entry_id: str,
        description: SHCSwitchEntityDescription,
        attr_name: str | None = None,
    ) -> None:
        """Initialize a SHC switch."""
        super().__init__(device, entry_id)
        self.entity_description = description
        self._attr_name = None if attr_name is None else attr_name
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}"
            if attr_name is None
            else f"{device.root_device_id}_{device.id}_{attr_name.lower()}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch.

        Defensive: cameras registered via SHC local API can have a None
        underlying service (e.g. PrivacyModeService for cameraeyes / camera360
        switches), causing boschshcpy to crash with AttributeError on every
        state update. Return None (unavailable) instead of crash-looping the
        state writer. See mosandlt/boschshc-hass branch fix/code-quality-improvements.
        """
        try:
            return (
                getattr(self._device, self.entity_description.on_key)
                == self.entity_description.on_value
            )
        except AttributeError:
            return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on.

        Guard against AttributeError: some devices (e.g. MicromoduleRelay with
        no connected load, Camera360 with no PrivacyMode service) expose a
        property whose underlying service is None.  Swallow and log instead of
        crash-looping the entity.  Fixes issues #185 (relay) and #206
        (camera_360).
        """
        try:
            await getattr(
                self._device,
                f"async_set_{self.entity_description.on_key}",
            )(True)
        except AttributeError:
            LOGGER.debug(
                "turn_on skipped for %s: service not available (no load/service?)",
                self.entity_id,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError):
            LOGGER.debug(
                "turn_on skipped for %s: service not available (no load/service?)",
                self.entity_id,
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off.

        Same guard as async_turn_on — see that docstring.
        """
        try:
            await getattr(
                self._device,
                f"async_set_{self.entity_description.on_key}",
            )(False)
        except AttributeError:
            LOGGER.debug(
                "turn_off skipped for %s: service not available (no load/service?)",
                self.entity_id,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError):
            LOGGER.debug(
                "turn_off skipped for %s: service not available (no load/service?)",
                self.entity_id,
            )

    @property
    def should_poll(self) -> bool:
        """Switch needs polling."""
        return self.entity_description.should_poll

    async def async_update(self) -> None:
        """Trigger an on-demand refresh of the device (async session).

        The integration runs SHCSessionAsync, so the device's sync update() would
        leave an un-awaited coroutine in the service state (TypeError on the next
        read, #335). Use the async refresh; fall back to the executor + sync
        update() only if the installed lib predates async_update.
        """
        if hasattr(self._device, "async_update"):
            await self._device.async_update()
        else:
            await self.hass.async_add_executor_job(self._device.update)


class SHCUserDefinedStateSwitch(SwitchEntity):
    """Representation of a SHC User Defined State Entity."""

    entity_description: SHCSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        device: SHCUserDefinedState,
        hass: HomeAssistant,
        session: SHCSession,
        entry_id: str,
        description: SHCSwitchEntityDescription,
        attr_name: str | None = None,
    ) -> None:
        """Initialize a SHC switch."""
        self._device = device
        self._session = session
        self._entry_id = entry_id
        self.entity_description = description
        # UDS entity: the state name IS the entity's distinguishing name.
        # With has_entity_name=True and _attr_name=None HA would show the SHC hub
        # name only; set _attr_name to the UDS state name so the entity is
        # identifiable (e.g. "Vacation Mode").
        self._attr_name = device.name if attr_name is None else attr_name

        self.entity_id = ENTITY_ID_FORMAT.format(
            f"userdefinedstate_{slugify(self._device.name)}"
        )
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}"
            if attr_name is None
            else f"{device.root_device_id}_{device.id}_{attr_name.lower()}"
        )
        self._shc: DeviceEntry = hass.data[DOMAIN][entry_id][DATA_SHC]

    async def async_added_to_hass(self):
        """Subscribe to SHC events."""
        await super().async_added_to_hass()

        def on_state_changed():
            self.schedule_update_ha_state()

        def update_entity_information():
            if self._device.deleted:
                self._attr_available = False
                # async_will_remove_from_hass must run on the event loop; this
                # callback fires from the SHC poll thread, so schedule it
                # thread-safely instead of hass.add_job (#288-cluster).
                self.hass.loop.call_soon_threadsafe(
                    self.hass.async_create_task,
                    self.async_will_remove_from_hass(),
                )
            self.schedule_update_ha_state()

        self._session.subscribe_userdefinedstate_callback(
            self._device.id, on_state_changed
        )
        self._session.subscribe_userdefinedstate_callback(
            self._device.id, update_entity_information
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe from SHC events."""
        await super().async_will_remove_from_hass()
        self._session.unsubscribe_userdefinedstate_callbacks(self._device.id)

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return (
            getattr(self._device, self.entity_description.on_key)
            == self.entity_description.on_value
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await getattr(
            self._device,
            f"async_set_{self.entity_description.on_key}",
        )(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await getattr(
            self._device,
            f"async_set_{self.entity_description.on_key}",
        )(False)

    @property
    def should_poll(self) -> bool:
        """Switch needs polling."""
        return self.entity_description.should_poll

    async def async_update(self) -> None:
        """Trigger an on-demand refresh of the device (async session).

        The sync device.update() leaves an un-awaited coroutine in the service
        state under SHCSessionAsync (TypeError, #335) — use the async refresh.
        """
        if hasattr(self._device, "async_update"):
            await self._device.async_update()
        else:
            await self.hass.async_add_executor_job(self._device.update)

    @property
    def device_name(self):
        """Name of the device."""
        return self._shc.name

    @property
    def device_id(self):
        """Device id of the entity."""
        return self._shc.id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": self._shc.identifiers,
            "name": self._shc.name,
            "manufacturer": self._shc.manufacturer,
            "model": self._shc.model,
        }
