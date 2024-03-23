"""DataUpdateCoordinator for the aurora_abb_powerone integration."""

import logging
from time import sleep

from aurorapy.client import AuroraError, AuroraSerialClient, AuroraTimeoutError
from serial import SerialException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AuroraAbbDataUpdateCoordinator(DataUpdateCoordinator[dict[str, float]]):  # pylint: disable=hass-enforce-coordinator-module
    """Class to manage fetching AuroraAbbPowerone data."""

    def __init__(self, hass: HomeAssistant, comport: str, address: int) -> None:
        """Initialize the data update coordinator."""
        self.available_prev = False
        self.available = False
        self.client = AuroraSerialClient(address, comport, parity="N", timeout=1)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    def _update_data(self) -> dict[str, float]:
        """Fetch new state data for the sensors.

        This is the only function that should fetch new data for Home Assistant.
        """
        data: dict[str, float] = {}
        self.available_prev = self.available
        retries: int = 3
        while retries > 0:
            try:
                self.client.connect()

                # read ADC channel 3 (grid power output)
                power_watts = self.client.measure(3, True)
                temperature_c = self.client.measure(21)
                energy_wh = self.client.cumulated_energy(5)
                [alarm, *_] = self.client.alarms()
            except AuroraTimeoutError:
                self.available = False
                _LOGGER.debug("No response from inverter (could be dark)")
                retries = 0
            except (SerialException, AuroraError) as error:
                self.available = False
                retries -= 1
                if retries <= 0:
                    raise UpdateFailed(error) from error
                _LOGGER.debug(
                    "Exception: %s occurred, %d retries remaining",
                    repr(error),
                    retries,
                )
                sleep(1)
            else:
                data["instantaneouspower"] = round(power_watts, 1)
                data["temp"] = round(temperature_c, 1)
                data["totalenergy"] = round(energy_wh / 1000, 2)
                data["alarm"] = alarm
                self.available = True
                retries = 0
            finally:
                if self.available != self.available_prev:
                    if self.available:
                        _LOGGER.info("Communication with %s back online", self.name)
                    else:
                        _LOGGER.info(
                            "Communication with %s lost",
                            self.name,
                        )
                if self.client.serline.isOpen():
                    self.client.close()

        return data

    async def _async_update_data(self) -> dict[str, float]:
        """Update inverter data in the executor."""
        return await self.hass.async_add_executor_job(self._update_data)
