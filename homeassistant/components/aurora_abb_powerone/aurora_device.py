"""Top level class for AuroraABBPowerOneSolarPV inverters and sensors."""
import logging

from aurorapy.client import AuroraError, AuroraSerialClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import ATTR_SERIAL_NUMBER, DEFAULT_DEVICE_NAME, DOMAIN, ICONS, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class AuroraDevice(Entity):
    """Representation of an Aurora ABB PowerOne device."""

    def __init__(
        self, device_params, client: AuroraSerialClient, config_entry: ConfigEntry
    ):
        """Initialise the basic device."""
        self.config_entry = config_entry
        self._id = config_entry.entry_id
        self.type = "device"
        # self._display_name = config_entry.
        self.serialnum = config_entry.data.get(ATTR_SERIAL_NUMBER, "dummy sn")
        self._sw_version = config_entry.data.get("firmware", "0.0.0")
        self._model = config_entry.data.get("pn", "Model unknown")
        self.client = client
        self.device_name = DEFAULT_DEVICE_NAME
        self._icon = ICONS.get(self.type)
        # self.should_poll(True)

    @property
    def unique_id(self) -> str:
        """Return the unique id for this device."""
        return slugify(f"{self.serialnum}_{self.type}")

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "config_entry_id": self._id,
            "identifiers": {(DOMAIN, self.serialnum)},
            "manufacturer": MANUFACTURER,
            "model": self._model,
            "name": self.device_name,
            "sw_version": self._sw_version,
        }

    def update(self):
        """Read data from the device."""
        try:
            self.client.connect()
            self.serialnum = self.client.serial_number()
            self._sw_version = self.client.firmware()
            self.name = self.client.pn()
        except AuroraError as error:
            # aurorapy does not have different exceptions (yet) for dealing
            # with timeout vs other comms errors.
            # This means the (normal) situation of no response during darkness
            # raises an exception.
            # aurorapy (gitlab) pull request merged 29/5/2019. When >0.2.6 is
            # released, this could be modified to :
            # except AuroraTimeoutError as e:
            # Workaround: look at the text of the exception
            if "No response after" in str(error):
                _LOGGER.debug("No response from inverter (could be dark)")
            else:
                raise error
        finally:
            if self.client.serline.isOpen():
                self.client.close()
