"""AVM FRITZ!Box connectivitiy sensor."""
import logging

from fritzconnection.core.exceptions import FritzConnectionException

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .common import FritzBoxHostEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up FRITZ!Box binary sensors")
    fritzbox_tools = hass.data[DOMAIN][entry.entry_id]

    if "WANIPConn1" in fritzbox_tools.connection.services:
        # Only routers are supported at the moment
        async_add_entities(
            [FritzBoxConnectivitySensor(fritzbox_tools, entry.title)], True
        )


class FritzBoxConnectivitySensor(FritzBoxHostEntity, BinarySensorEntity):
    """Define FRITZ!Box connectivity class."""

    def __init__(self, fritzbox_tools, device_friendlyname: str):
        """Init FRITZ!Box connectivity class."""
        self._fritzbox_tools = fritzbox_tools
        self._unique_id = f"{self._fritzbox_tools.unique_id}-connectivity"
        self._model = self._fritzbox_tools._model
        self._name = f"{device_friendlyname} Connectivity"
        self._is_on = True
        self._is_available = True
        self._attributes: dict = {}
        super().__init__()

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def device_class(self):
        """Return device class."""
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return status."""
        return self._is_on

    @property
    def unique_id(self):
        """Return unique id."""
        return self._unique_id

    @property
    def mac_address(self) -> str:
        """Return the mac address of the main device."""
        return self._fritzbox_tools.mac

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._is_available

    @property
    def device_state_attributes(self) -> dict:
        """Return device attributes."""
        return self._attributes

    def update(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating FRITZ!Box binary sensors")
        self._is_on = True
        try:
            if "WANCommonInterfaceConfig1" in self._fritzbox_tools.connection.services:
                link_props = self._fritzbox_tools.connection.call_action(
                    "WANCommonInterfaceConfig1", "GetCommonLinkProperties"
                )
                is_up = link_props["NewPhysicalLinkStatus"]
                self._is_on = is_up == "Up"
            else:
                self._is_on = self._fritzbox_tools.fritzstatus.is_connected

            self._is_available = True

        except FritzConnectionException:
            _LOGGER.error("Error getting the state from the FRITZ!Box", exc_info=True)
            self._is_available = False
