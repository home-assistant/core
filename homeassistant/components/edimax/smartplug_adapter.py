"""Support for Edimax sensors."""

from dataclasses import dataclass

from pyedimax.smartplug import SmartPlug

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DEFAULT_NAME, DEFAULT_PASSWORD, DEFAULT_USER_NAME


@dataclass
class Info:
    """Info class containing serial_number."""

    serial_number: str
    product_name: str
    display_name: str
    version: str


@dataclass
class EdimaxData:
    """Edimax status data."""

    info: Info
    now_power: float
    total_energy_day: float
    is_on: bool


class SmartPlugAdapter:
    """Edimax SmartPlug Updater."""

    hass: HomeAssistant
    host: str
    name: str

    client: SmartPlug = None
    info: Info
    data: EdimaxData

    #    def __init__(self, smartPlug: SmartPlug) -> None:
    #        pass

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        name: str = DEFAULT_NAME,
    ) -> None:
        """Init Smartplug Adapter."""

        self.hass = hass
        self.host = host
        self.auth = (DEFAULT_USER_NAME, DEFAULT_PASSWORD)

        self.name = name

    def update(self) -> None:
        """Fetch data from the Edimax device."""

        if self.client is None:
            self.client = SmartPlug(self.host, self.auth)

        try:
            self.info = Info(
                display_name="Edimax SmartPlug",
                serial_number=self.client.info["mac"],
                version=self.client.info["version"],
                product_name=self.client.info["model"],
            )

            self.data = EdimaxData(
                info=self.info,
                now_power=self.client.now_power,
                total_energy_day=self.client.now_energy_day,
                is_on=self.client.state == "ON",
            )
        except ConnectionError as err:
            raise UpdateFailed(err) from err

    async def async_update(self) -> None:
        """Update status asynchronously."""
        await self.hass.async_add_executor_job(self.update)

    @property
    def total_energy_day(self) -> float:
        """Get the total energy for the day in kwh for the SmartPlug. Only works on SP-2101W.

        :type self: object
        :rtype: float
        :return: Current power usage for the day in kwh
        """

        return self.data.total_energy_day

    @property
    def now_power(self) -> float:
        """Get the power for the day in kwh for the SmartPlug. Only works on SP-2101W.

        :type self: object
        :rtype: float
        :return: Current power usage for the day in kwh
        """

        return self.data.now_power

    @property
    def state(self) -> str:
        """Get the current state of the SmartPlug.

        :type self: object
        :rtype: str
        :return: 'ON' or 'OFF'
        """

        if self.data.is_on:
            return "ON"

        return "OFF"

    @state.setter
    def state(self, value):
        """Set the state of the SmartPlug.

        :type self: object
        :type value: str
        :param value: 'ON', 'on', 'OFF' or 'off'
        """

        if value not in ("ON", "on", "OFF", "off"):
            raise EdimaxSmartPlugException(
                "Failed to communicate with SmartPlug: Invalid Value"
            )

        self.client.state = value


class EdimaxSmartPlugException(Exception):
    """Custom Exception for SmartPlugAdapter."""
