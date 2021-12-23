"""Platform for switch integration."""
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

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity

SWITCH_TYPES: dict[str, SwitchEntityDescription] = {
    "smartplug": SwitchEntityDescription(
        key="smartplug",
        device_class=SwitchDeviceClass.OUTLET,
    ),
    "smartplugcompact": SwitchEntityDescription(
        key="smartplugcompact",
        device_class=SwitchDeviceClass.OUTLET,
    ),
    "lightswitch": SwitchEntityDescription(
        key="lightswitch",
        device_class=SwitchDeviceClass.SWITCH,
    ),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the SHC switch platform."""
    entities = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for switch in session.device_helper.smart_plugs:

        entities.append(
            SmartPlugSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["smartplug"],
            )
        )

    for switch in session.device_helper.light_switches:

        entities.append(
            LightSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["lightswitch"],
            )
        )

    for switch in session.device_helper.smart_plugs_compact:

        entities.append(
            SmartPlugCompactSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
                description=SWITCH_TYPES["smartplugcompact"],
            )
        )

    for switch in session.device_helper.camera_eyes:

        entities.append(
            CameraEyesSwitch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    for switch in session.device_helper.camera_360:

        entities.append(
            Camera360Switch(
                device=switch,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    if entities:
        async_add_entities(entities)


class SHCSwitch(SHCEntity, SwitchEntity):
    """Representation of a SHC switch."""

    def __init__(
        self,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize a SHC switch."""
        super().__init__(device, parent_id, entry_id)
        self.entity_description = description

    @property
    def device_class(self):
        """Return the class of this device."""
        return self.entity_description.device_class

    @property
    def today_energy_kwh(self):
        """Return the total energy usage in kWh."""
        return self._device.energyconsumption / 1000.0

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._device.powerconsumption

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._device.state = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._device.state = False

    def toggle(self, **kwargs):
        """Toggle the switch."""
        self._device.state = not self.is_on


class SHCCameraSwitch(SHCEntity, SwitchEntity):
    """Representation of a SHC camera switch."""

    @property
    def device_class(self):
        """Return the class of this device."""
        return SwitchDeviceClass.SWITCH

    @property
    def should_poll(self):
        """Camera 360 needs polling."""
        return True

    def update(self):
        """Trigger an update of the device."""
        self._device.update()


class SmartPlugSwitch(SHCSwitch):
    """Representation of a SHC smart plug switch."""

    def __init__(
        self,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize a smart plug switch."""
        super().__init__(device, parent_id, entry_id, description)

    @property
    def is_on(self):
        """Return the switch state is currently on or off."""
        return self._device.state == SHCSmartPlug.PowerSwitchService.State.ON

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "routing": self._device.routing.name,
        }


class LightSwitch(SHCSwitch):
    """Representation of a SHC light switch."""

    def __init__(
        self,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize a light switch."""
        super().__init__(device, parent_id, entry_id, description)

    @property
    def is_on(self):
        """Return the switch state is currently on or off."""
        return self._device.state == SHCLightSwitch.PowerSwitchService.State.ON


class SmartPlugCompactSwitch(SHCSwitch):
    """Representation of a smart plug compact switch."""

    def __init__(
        self,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize a smart plug compact switch."""
        super().__init__(device, parent_id, entry_id, description)

    @property
    def is_on(self):
        """Return the switch state is currently on or off."""
        return self._device.state == SHCSmartPlugCompact.PowerSwitchService.State.ON

    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "communication_quality": self._device.communicationquality.name,
        }


class CameraEyesSwitch(SHCCameraSwitch):
    """Representation of camera eyes as switch."""

    def __init__(
        self,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize a camera eyes switch."""
        super().__init__(device, parent_id, entry_id)

    @property
    def is_on(self):
        """Return the state of the switch."""
        return self._device.cameralight == SHCCameraEyes.CameraLightService.State.ON

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._device.cameralight = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._device.cameralight = False

    def toggle(self, **kwargs):
        """Toggle the switch."""
        self._device.state = not self.is_on


class Camera360Switch(SHCCameraSwitch):
    """Representation of camera 360 as switch."""

    def __init__(
        self,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize a camera 360 switch."""
        super().__init__(device, parent_id, entry_id)

    @property
    def is_on(self):
        """Return the state of the switch."""
        return (
            self._device.privacymode == SHCCamera360.PrivacyModeService.State.DISABLED
        )

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._device.privacymode = False

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._device.privacymode = True

    def toggle(self, **kwargs):
        """Toggle the switch."""
        self._device.privacymode = not self.is_on
