"""EVSE Wifi Class to set and get Parameters on the EVSE-Wifi Device."""

import asyncio
import logging

import async_timeout
import httpx

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EVSE:
    """EVSE Wifi class."""

    def __init__(
        self, host: str, name: str, max_current: int, interval: int = 30
    ) -> None:
        """Initialize."""
        self.host = host
        self.name = name
        self.max_current = max_current
        self.interval = interval
        self.parameters = None
        self.devcie_info = DeviceInfo(
            identifiers={(DOMAIN, self.name)},
            name=self.name,
            model="SimpleEVSE",
            configuration_url=f"http://{self.host}/",
            via_device=(DOMAIN, self.host),
        )

    async def get_parameters(self):
        """Get parameters from EVSE Wifi Device."""
        try:
            url = f"http://{self.host}/getParameters"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                self.parameters = response.json()
            return response
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("EVSE getParameters Exception: %s", exception)

    async def test(self) -> bool:
        """Testing the Integration by try getting the Parameters."""
        response = await self.get_parameters()
        if response.status_code == 200:
            return True
        return False

    async def set_current(self, current: int) -> bool:
        """Set the charging current."""
        try:
            if current <= self.max_current:
                url = f"http://{self.host}/setCurrent?current={current}"
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        await asyncio.sleep(2)
                        async with async_timeout.timeout(10):
                            await self.get_parameters()
                            return True
            return False
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("EVSE set_current Exception: %s", exception)
            return False

    async def set_status(self, status: bool) -> bool:
        """Set the evse status."""
        try:
            if status is True:
                url = f"http://{self.host}/setStatus?active=true"
            else:
                url = f"http://{self.host}/setStatus?active=false"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 200:
                    await asyncio.sleep(2)
                    async with async_timeout.timeout(10):
                        await self.get_parameters()
                        return True
            return False
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("EVSE set_status Exception: %s", exception)
            return False

    async def do_reboot(self) -> bool:
        """Perform a reboot of the EVSE Wifi Device."""
        try:
            url = f"http://{self.host}/doReboot?reboot=true"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return True
            return False
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("EVSE do_reboot Exception: %s", exception)
            return False

    def get_vehicle_state(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("vehicleState")

    def get_evse_state(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("evseState")

    def get_max_current(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("maxCurrent")

    def get_actual_current(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("actualCurrent")

    def get_actual_power(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("actualPower")

    def get_duration(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("duration")

    def get_always_active(self):
        """Return the Value."""
        if self.parameters is not None:
            always_active = self.parameters.get("list")[0].get("alwaysActive")
            if always_active is True:
                return 1
            return 0

    def get_last_action_user(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("lastActionUser")

    def get_last_action_uid(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("lastActionUID")

    def get_energy(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("energy")

    def get_milage(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("mileage")

    def get_meter_reading(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("meterReading")

    def get_current_p1(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("currentP1")

    def get_current_p2(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("currentP2")

    def get_current_p3(self):
        """Return the Value."""
        if self.parameters is not None:
            return self.parameters.get("list")[0].get("currentP3")

    def get_use_meter(self):
        """Return the Value."""
        if self.parameters is not None:
            use_meter = self.parameters.get("list")[0].get("useMeter")
            if use_meter is True:
                return 1
            return 0
