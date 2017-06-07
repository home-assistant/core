"""
homeassistant.components.option.cec
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CEC platform that handles options.
"""
# Because we do not compile cec on CI
# pylint: disable=import-error
import homeassistant.components.cec as cec

from homeassistant.components.option import OptionDevice


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Find and return demo switches. """

    cec_option = CecOption(hass)

    hass.bus.listen_once(cec.EVENT_CEC_DEVICE_CHANGED, lambda event: cec_option.update_ha_state(True))

    print("cec OPTION setup_platform", hass, config, add_devices, discovery_info)
    if discovery_info is None:
        return

    add_devices([cec_option])


class CecOption(OptionDevice):
    def __init__(self, hass):
        self._hass = hass
        self._option = None
        self._options = []

    @property
    def option(self):
        """ Returns the active option of the entity. """
        return self._option

    @property
    def options(self):
        """ Returns the list of available options for this entity. """
        return self._options

    def switch(self, option, **kwargs):
        """ Select the option 'option' for this entity. """
        for d in cec.DEVICES.values():
            if d.osd == option:
                data = {cec.ATTR_CEC_PHYSICAL_ADDRESS: d.physical_address}
                self._hass.services.call(cec.DOMAIN, cec.SERVICE_CEC_SET_STREAM_PATH, data)
                return True
        return False

    def update(self):
        self._options = [d.osd for d in cec.DEVICES.values()]
        active_device = next(filter(lambda d: d.active, cec.DEVICES.values()), None)
        self._option = active_device.osd if active_device else None
