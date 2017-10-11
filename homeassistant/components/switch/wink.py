"""
Support for Wink switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.wink/
"""
import asyncio
import logging
from os import path

import voluptuous as vol

from homeassistant.components.wink import WinkDevice, DOMAIN
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.config import load_yaml_config_file

DEPENDENCIES = ['wink']

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_CHIME_VOLUME = "wink_set_chime_volume"
SERVICE_SET_SIREN_VOLUME = "wink_set_siren_volume"
SERVICE_ENABLE_CHIME = "wink_enable_chime"
SERVICE_SET_SIREN_TONE = "wink_set_siren_tone"
SERVICE_SET_SIREN_AUTO_SHUTOFF = "wink_siren_set_auto_shutoff"
SERVICE_SET_SIREN_STROBE_ENABLED = "wink_set_siren_strobe_enabled"
SERVICE_SET_CHIME_STROBE_ENABLED = "wink_set_chime_strobe_enabled"

ATTR_VOLUME = "volume"
ATTR_TONE = "tone"
ATTR_ENABLED = "enabled"
ATTR_AUTO_SHUTOFF = "auto_shutoff"

VOLUMES = ["low", "medium", "high"]
TONES = ["doorbell", "fur_elise", "doorbell_extended", "alert",
         "william_tell", "rondo_alla_turca", "police_siren",
         "evacuation", "beep_beep", "beep"]
CHIME_TONES = TONES + ["inactive"]
AUTO_SHUTOFF_TIMES = [None, -1, 30, 60, 120]


SET_VOLUME_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_VOLUME): vol.In(VOLUMES)
})

SET_SIREN_TONE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_TONE): vol.In(TONES)
})

SET_CHIME_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_TONE): vol.In(CHIME_TONES)
})

SET_AUTO_SHUTOFF_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_AUTO_SHUTOFF): vol.In(AUTO_SHUTOFF_TIMES)
})

SET_STROBE_ENABLED_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_ENABLED): cv.boolean
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Wink platform."""
    import pywink

    def service_handle(service):
        """Handler for services."""
        entity_ids = service.data.get('entity_id')
        all_sirens = []
        for switch in hass.data[DOMAIN]['entities']['switch']:
            if isinstance(switch, WinkSirenDevice):
                all_sirens.append(switch)
        sirens_to_set = []
        if entity_ids is None:
            sirens_to_set = all_sirens
        else:
            for siren in all_sirens:
                if siren.entity_id in entity_ids:
                    sirens_to_set.append(siren)

        for siren in sirens_to_set:
            if service.service != SERVICE_SET_SIREN_AUTO_SHUTOFF:
                if siren.wink.device_manufacturer() != 'dome':
                    _LOGGER.error("Service only valid for Dome sirens.")
                    return
                if service.service == SERVICE_SET_CHIME_VOLUME:
                    siren.wink.set_chime_volume(service.data.get(ATTR_VOLUME))
                elif service.service == SERVICE_SET_SIREN_VOLUME:
                    siren.wink.set_siren_volume(service.data.get(ATTR_VOLUME))
                elif service.service == SERVICE_SET_SIREN_TONE:
                    siren.wink.set_siren_sound(service.data.get(ATTR_TONE))
                elif service.service == SERVICE_ENABLE_CHIME:
                    siren.wink.set_chime(service.data.get(ATTR_TONE))
                elif service.service == SERVICE_SET_SIREN_STROBE_ENABLED:
                    siren.wink.set_siren_strobe_enabled(
                        service.data.get(ATTR_ENABLED))
                elif service.service == SERVICE_SET_CHIME_STROBE_ENABLED:
                    siren.wink.set_chime_strobe_enabled(
                        service.data.get(ATTR_ENABLED))
            else:
                siren.wink.set_auto_shutoff(
                    service.data.get(ATTR_AUTO_SHUTOFF))

    for switch in pywink.get_switches():
        _id = switch.object_id() + switch.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkToggleDevice(switch, hass)])
    for switch in pywink.get_powerstrips():
        _id = switch.object_id() + switch.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkToggleDevice(switch, hass)])
    for siren in pywink.get_sirens():
        _id = siren.object_id() + siren.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkSirenDevice(siren, hass)])
    for sprinkler in pywink.get_sprinklers():
        _id = sprinkler.object_id() + sprinkler.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkToggleDevice(sprinkler, hass)])
    for switch in pywink.get_binary_switch_groups():
        _id = switch.object_id() + switch.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkToggleDevice(switch, hass)])

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, SERVICE_SET_SIREN_TONE,
                           service_handle,
                           descriptions.get(SERVICE_SET_SIREN_TONE),
                           schema=SET_SIREN_TONE_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_ENABLE_CHIME,
                           service_handle,
                           descriptions.get(SERVICE_ENABLE_CHIME),
                           schema=SET_CHIME_MODE_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_SET_SIREN_VOLUME,
                           service_handle,
                           descriptions.get(SERVICE_SET_SIREN_VOLUME),
                           schema=SET_VOLUME_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_SET_CHIME_VOLUME,
                           service_handle,
                           descriptions.get(SERVICE_SET_CHIME_VOLUME),
                           schema=SET_VOLUME_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_SET_SIREN_STROBE_ENABLED,
                           service_handle,
                           descriptions.get(SERVICE_SET_SIREN_STROBE_ENABLED),
                           schema=SET_STROBE_ENABLED_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_SET_CHIME_STROBE_ENABLED,
                           service_handle,
                           descriptions.get(SERVICE_SET_CHIME_STROBE_ENABLED),
                           schema=SET_STROBE_ENABLED_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_SET_SIREN_AUTO_SHUTOFF,
                           service_handle,
                           descriptions.get(SERVICE_SET_SIREN_AUTO_SHUTOFF),
                           schema=SET_AUTO_SHUTOFF_SCHEMA)


class WinkToggleDevice(WinkDevice, ToggleEntity):
    """Representation of a Wink toggle device."""

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Callback when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['switch'].append(self)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.wink.state()

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.wink.set_state(True)

    def turn_off(self):
        """Turn the device off."""
        self.wink.set_state(False)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = super(WinkToggleDevice, self).device_state_attributes
        try:
            event = self.wink.last_event()
            if event is not None:
                attributes["last_event"] = event
        except AttributeError:
            pass
        return attributes


class WinkSirenDevice(WinkDevice, ToggleEntity):
    """Representation of a Wink siren device."""

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Callback when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['switch'].append(self)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.wink.state()

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.wink.set_state(True)

    def turn_off(self):
        """Turn the device off."""
        self.wink.set_state(False)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = super(WinkSirenDevice, self).device_state_attributes

        auto_shutoff = self.wink.auto_shutoff()
        if auto_shutoff is not None:
            attributes["auto_shutoff"] = auto_shutoff

        siren_volume = self.wink.siren_volume()
        if siren_volume is not None:
            attributes["siren_volume"] = siren_volume

        chime_volume = self.wink.chime_volume()
        if chime_volume is not None:
            attributes["chime_volume"] = chime_volume

        strobe_enabled = self.wink.strobe_enabled()
        if strobe_enabled is not None:
            attributes["siren_strobe_enabled"] = strobe_enabled

        chime_strobe_enabled = self.wink.chime_strobe_enabled()
        if chime_strobe_enabled is not None:
            attributes["chime_strobe_enabled"] = chime_strobe_enabled

        siren_sound = self.wink.siren_sound()
        if siren_sound is not None:
            attributes["siren_sound"] = siren_sound

        chime_mode = self.wink.chime_mode()
        if chime_mode is not None:
            attributes["chime_mode"] = chime_mode

        return attributes
