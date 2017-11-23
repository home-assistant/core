"""
Support for AppliedSensor iAQStick

On Linux, a custom udev rule is needed, add a file
/etc/udev/rules.d/99-iaqstick.rules containing

SUBSYSTEM=="usb", ATTR{idVendor}=="03eb", ATTR{idProduct}=="2013", MODE="666"

and run # udevadm control --reload-rules && udevadm trigger or reboot.

"""

import logging
import usb.core
import usb.util

from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyusb>=1.0.0']

logger = logging.getLogger('iAQStick')


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the air sensor platform"""
    add_devices([iAQStick()])


class iAQStick(Entity):

    initialized = False

    ppm = 0

    def __init__(self):
        self._dev = usb.core.find(idVendor=0x03eb, idProduct=0x2013)
        if self._dev is None:
            logger.error("iAQ Stick not found")
            return
        self._intf = 0
        self._type2_seq = 0x67

        try:
            if self._dev.is_kernel_driver_active(self._intf):
                self._dev.detach_kernel_driver(self._intf)

            self._dev.set_configuration(0x01)
            usb.util.claim_interface(self._dev, self._intf)
            self._dev.set_interface_altsetting(self._intf, 0x00)
            logger.error("initialized")

        except Exception as e:
            logger.error("init interface failed - {}".format(e))
        self.initialized = True
        self._state = None
        self.update()

    @property
    def name(self):
        """Returns ame of the sensor"""
        return "AppliedSensor iAQStick"

    @property
    def state(self):
        """Returns the state of the sensor"""
        return self._state

    @property
    def unit_of_measurement(self):
        """Returns the unit of measurement: parts per million"""
        return "ppm"

    @property
    def should_poll(self):
        return True

    def xfer_type2(self, msg):
        out_data = bytes('@', 'utf-8') + \
            self._type2_seq.to_bytes(1,
                                    byteorder='big') + \
                                    bytes('{}\n@@@@@@@@@@@@@'.format(msg),
                                    'utf-8')
        self._type2_seq = (self._type2_seq + 1) if (self._type2_seq < 0xFF) \
            else 0x67
        ret = self._dev.write(0x02, out_data[:16])
        in_data = bytes()
        while True:
            ret = bytes(self._dev.read(0x81, 0x10))
            if len(ret) == 0:
                break
            in_data += ret
        return in_data

    def stop(self):
        if not self.initialized:
            return
        self.alive = False
        try:
            usb.util.release_interface(self._dev, self._intf)
        except Exception as e:
            logger.error("release interface failed - {}".format(e))

    def update(self):

        if not self.initialized:
            return
        try:
            meas = self.xfer_type2('*TR')
            ppm = int.from_bytes(meas[2:4], byteorder='little')
            self.ppm = ppm
            self._state = ppm
        except Exception as e:
            logger.error("update failed - {}".format(e))
            self._state = 99

    def state_string(self):
        if self.ppm > 1500:
            return 'Bad'
        elif self.ppm > 1000:
            return 'Mediocre'
        elif self.ppm > 500:
            return 'Decent'
        elif self.ppm > 400:
            return 'Good'
        else:
            return "Invalid Measurement"
