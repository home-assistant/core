"""AVM FRITZ!Box connectivitiy sensor."""
import datetime
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

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

    return True


class FritzBoxConnectivitySensor(BinarySensorEntity):
    """Define FRITZ!Box connectivity class."""

    def __init__(self, fritzbox_tools, device_friendlyname: str):
        """Init FRITZ!Box connectivity class."""
        self._fritzbox_tools = fritzbox_tools
        self._unique_id = f"{self._fritzbox_tools.unique_id}-{self.entity_id}"
        self._name = f"{device_friendlyname} Connectivity"
        self._is_on = True
        self._is_available = True
        self._attributes = {}
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
    def device_info(self):
        """Return device info."""
        return self._fritzbox_tools.device_info

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._is_available

    @property
    def device_state_attributes(self) -> dict:
        """Return device attributes."""
        return self._attributes

    def _connection_call_action(self):
        return lambda: self._fritzbox_tools.connection.call_action(
            "WANCommonInterfaceConfig1", "GetCommonLinkProperties"
        )["NewPhysicalLinkStatus"]

    async def _async_fetch_update(self):
        """Fetch updates."""
        self._is_on = True
        try:
            if "WANCommonInterfaceConfig1" in self._fritzbox_tools.connection.services:
                connection = self._connection_call_action()
                is_up = await self.hass.async_add_executor_job(connection)
                self._is_on = is_up == "Up"
            else:
                self._is_on = self.hass.async_add_executor_job(
                    self._fritzbox_tools.fritzstatus.is_connected
                )

            self._is_available = True

            status = self._fritzbox_tools.fritzstatus
            uptime_seconds = await self.hass.async_add_executor_job(
                lambda: getattr(status, "uptime")
            )
            last_reconnect = datetime.datetime.now() - datetime.timedelta(
                seconds=uptime_seconds
            )
            self._attributes["last_reconnect"] = last_reconnect.replace(
                microsecond=0
            ).isoformat()

            if ipv4_address := await self.hass.async_add_executor_job(
                lambda: getattr(status, "external_ip")
            ):
                self._attributes["external_ip"] = ipv4_address

            if ipv6_address := await self.hass.async_add_executor_job(
                lambda: getattr(status, "external_ipv6")
            ):
                self._attributes["external_ip"] = ipv6_address

        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Error getting the state from the FRITZ!Box", exc_info=True)
            self._is_available = False

    async def async_update(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating FRITZ!Box binary sensors")
        await self._async_fetch_update()
