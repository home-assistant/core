"""Support for HDMI CEC devices as switches."""
import logging

from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON

from . import ATTR_NEW, CecEntity

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Find and return HDMI devices as switches."""
    if ATTR_NEW in discovery_info:
        _LOGGER.info("Setting up HDMI devices %s", discovery_info[ATTR_NEW])
        entities = []
        for device in discovery_info[ATTR_NEW]:
            hdmi_device = hass.data.get(device)
            entities.append(CecSwitchEntity(hdmi_device, hdmi_device.logical_address))
        add_entities(entities, True)


class CecSwitchEntity(CecEntity, SwitchEntity):
    """Representation of a HDMI device as a Switch."""

    def __init__(self, device, logical) -> None:
        """Initialize the HDMI device."""
        CecEntity.__init__(self, device, logical)
        self.entity_id = f"{DOMAIN}.hdmi_{hex(self._logical_address)[2:]}"

    def turn_on(self, **kwargs) -> None:
        """Turn device on."""
        self._device.turn_on()
        self._state = STATE_ON
        self.schedule_update_ha_state(force_refresh=False)

    def turn_off(self, **kwargs) -> None:
        """Turn device off."""
        self._device.turn_off()
        self._state = STATE_OFF
        self.schedule_update_ha_state(force_refresh=False)

    def toggle(self, **kwargs):
        """Toggle the entity."""
        self._device.toggle()
        if self._state == STATE_ON:
            self._state = STATE_OFF
        else:
            self._state = STATE_ON
        self.schedule_update_ha_state(force_refresh=False)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._state == STATE_ON

    @property
    def state(self) -> str:
        """Return the cached state of device."""
        return self._state
