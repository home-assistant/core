"""This component provides support many for Reolink IP cameras switches."""
import asyncio
import logging

from homeassistant.components.switch import DEVICE_CLASS_SWITCH
from homeassistant.helpers.entity import ToggleEntity

from .const import BASE, DOMAIN
from .entity import ReolinkEntity

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the Reolink IP Camera switches."""
    devices = []
    base = hass.data[DOMAIN][config_entry.entry_id][BASE]

    for capability in await base.api.get_switch_capabilities():
        if capability == "ftp":
            devices.append(FTPSwitch(hass, config_entry))
        elif capability == "email":
            devices.append(EmailSwitch(hass, config_entry))
        elif capability == "audio":
            devices.append(AudioSwitch(hass, config_entry))
        elif capability == "irLights":
            devices.append(IRLightsSwitch(hass, config_entry))
        elif capability == "recording":
            devices.append(RecordingSwitch(hass, config_entry))
        else:
            continue

    async_add_devices(devices, update_before_add=False)


class FTPSwitch(ReolinkEntity, ToggleEntity):
    """An implementation of a Reolink IP camera FTP switch."""

    def __init__(self, hass, config):
        """Initialize a Reolink camera."""
        ReolinkEntity.__init__(self, hass, config)
        ToggleEntity.__init__(self)

    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"reolink_ftpSwitch_{self._base.api.mac_address}"

    @property
    def name(self):
        """Return the name of this camera."""
        return f"{self._base.api.name} FTP"

    @property
    def is_on(self):
        """Camera Motion FTP upload Status."""
        return self._base.api.ftp_state

    @property
    def device_class(self):
        """Device class of the switch."""
        return DEVICE_CLASS_SWITCH

    @property
    def icon(self):
        """Icon of the switch."""
        if self.is_on:
            return "mdi:folder-upload"

        return "mdi:folder-remove"

    async def async_turn_on(self, **kwargs):
        """Enable motion ftp recording."""
        await self._base.api.set_ftp(True)
        await self.request_refresh()

    async def async_turn_off(self, **kwargs):
        """Disable motion ftp recording."""
        await self._base.api.set_ftp(False)
        await self.request_refresh()


class EmailSwitch(ReolinkEntity, ToggleEntity):
    """An implementation of a Reolink IP camera email switch."""

    def __init__(self, hass, config):
        """Initialize a Reolink camera."""
        ReolinkEntity.__init__(self, hass, config)
        ToggleEntity.__init__(self)

    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"reolink_emailSwitch_{self._base.api.mac_address}"

    @property
    def name(self):
        """Return the name of this camera."""
        return f"{self._base.api.name} email"

    @property
    def is_on(self):
        """Camera Motion email upload Status."""
        return self._base.api.email_state

    @property
    def device_class(self):
        """Device class of the switch."""
        return DEVICE_CLASS_SWITCH

    @property
    def icon(self):
        """Icon of the switch."""
        if self.is_on:
            return "mdi:email"

        return "mdi:email-outline"

    async def async_turn_on(self, **kwargs):
        """Enable motion email notification."""
        await self._base.api.set_email(True)
        await self.request_refresh()

    async def async_turn_off(self, **kwargs):
        """Disable motion email notification."""
        await self._base.api.set_email(False)
        await self.request_refresh()


class IRLightsSwitch(ReolinkEntity, ToggleEntity):
    """An implementation of a Reolink IP camera ir lights switch."""

    def __init__(self, hass, config):
        """Initialize a Reolink camera."""
        ReolinkEntity.__init__(self, hass, config)
        ToggleEntity.__init__(self)

    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"reolink_irLightsSwitch_{self._base.api.mac_address}"

    @property
    def name(self):
        """Return the name of this camera."""
        return f"{self._base.api.name} IR lights"

    @property
    def is_on(self):
        """Camera Motion ir lights Status."""
        return self._base.api.ir_state

    @property
    def device_class(self):
        """Device class of the switch."""
        return DEVICE_CLASS_SWITCH

    @property
    def icon(self):
        """Icon of the switch."""
        if self.is_on:
            return "mdi:flashlight"

        return "mdi:flashlight-off"

    async def async_turn_on(self, **kwargs):
        """Enable motion ir lights."""
        await self._base.api.set_ir_lights(True)
        await self.request_refresh()

    async def async_turn_off(self, **kwargs):
        """Disable motion ir lights."""
        await self._base.api.set_ir_lights(False)
        await self.request_refresh()


class RecordingSwitch(ReolinkEntity, ToggleEntity):
    """An implementation of a Reolink IP camera recording switch."""

    def __init__(self, hass, config):
        """Initialize a Reolink camera."""
        ReolinkEntity.__init__(self, hass, config)
        ToggleEntity.__init__(self)

    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"reolink_recordingSwitch_{self._base.api.mac_address}"

    @property
    def name(self):
        """Return the name of this camera."""
        return f"{self._base.api.name} recording"

    @property
    def is_on(self):
        """Camera recording upload Status."""
        return self._base.api.recording_state

    @property
    def device_class(self):
        """Device class of the switch."""
        return DEVICE_CLASS_SWITCH

    @property
    def icon(self):
        """Icon of the switch."""
        if self.is_on:
            return "mdi:filmstrip"

        return "mdi:filmstrip-off"

    async def async_turn_on(self, **kwargs):
        """Enable recording."""
        await self._base.api.set_recording(True)
        await self.request_refresh()

    async def async_turn_off(self, **kwargs):
        """Disable recording."""
        await self._base.api.set_recording(False)
        await self.request_refresh()


class AudioSwitch(ReolinkEntity, ToggleEntity):
    """An implementation of a Reolink IP camera audio switch."""

    def __init__(self, hass, config):
        """Initialize a Reolink camera."""
        ReolinkEntity.__init__(self, hass, config)
        ToggleEntity.__init__(self)

    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"reolink_audioSwitch_{self._base.api.mac_address}"

    @property
    def name(self):
        """Return the name of this camera."""
        return f"{self._base.api.name} record audio"

    @property
    def is_on(self):
        """Camera audio switch Status."""
        return self._base.api.audio_state

    @property
    def device_class(self):
        """Device class of the switch."""
        return DEVICE_CLASS_SWITCH

    @property
    def icon(self):
        """Icon of the switch."""
        if self.is_on:
            return "mdi:volume-high"

        return "mdi:volume-off"

    async def async_turn_on(self, **kwargs):
        """Enable audio recording."""
        await self._base.api.set_audio(True)
        await self.request_refresh()

    async def async_turn_off(self, **kwargs):
        """Disable audio recording."""
        await self._base.api.set_audio(False)
        await self.request_refresh()
