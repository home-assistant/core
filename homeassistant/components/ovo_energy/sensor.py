"""Support for OVO Energy sensors."""
from datetime import datetime, timedelta
import logging

import aiohttp
from ovoenergy import OVODailyElectricity, OVODailyGas, OVODailyUsage
from ovoenergy.ovoenergy import OVOEnergy

from homeassistant.components.ovo_energy import OVOEnergyDeviceEntity
from homeassistant.components.ovo_energy.const import (
    CONF_ACCOUNT_ID,
    DATA_OVO_ENERGY_CLIENT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up OVO Energy sensor based on a config entry."""
    instance_key = f"{DOMAIN}_{entry.data[CONF_ACCOUNT_ID]}"
    client = hass.data[instance_key][DATA_OVO_ENERGY_CLIENT]

    now = datetime.utcnow()
    try:
        await client.get_daily_usage(now.strftime("%Y-%m"))
    except aiohttp.ClientError as exception:
        _LOGGER.warning(exception)
        raise PlatformNotReady from exception

    sensors = [
        OVOEnergyLastElectricityReading(client),
        OVOEnergyLastGasReading(client),
    ]

    async_add_entities(sensors, True)


class OVOEnergySensor(OVOEnergyDeviceEntity):
    """Defines a OVO Energy sensor."""

    def __init__(
        self,
        client: OVOEnergy,
        key: str,
        name: str,
        icon: str,
        unit_of_measurement: str = "",
    ) -> None:
        """Initialize OVO Energy sensor."""
        self._state = None
        self._attributes = None
        self._available = False
        self._unit_of_measurement = unit_of_measurement

        super().__init__(client, key, name, icon)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return self._key

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        return self._attributes

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class OVOEnergyLastElectricityReading(OVOEnergySensor):
    """Defines a OVO Energy card count sensor."""

    def __init__(self, client):
        """Initialize OVO Energy sensor."""

        super().__init__(
            client,
            f"{DOMAIN}_{client.account_id}_last_electricity_reading",
            "OVO Last Electricity Reading",
            "mdi:flash",
            "kWh",
        )

    async def _ovo_energy_update(self) -> bool:
        """Update OVO Energy entity."""
        now = datetime.utcnow()
        try:
            usage: OVODailyUsage = await self._client.get_daily_usage(
                now.strftime("%Y-%m")
            )
            if usage is None or usage.electricity is None:
                _LOGGER.warning("No data found for %s", self._name)
                self._available = False
            last_reading: OVODailyElectricity = usage.electricity[
                len(usage.electricity) - 1
            ]
            self._state = last_reading.consumption
            self._attributes = {
                "start_time": last_reading.interval.start,
                "end_time": last_reading.interval.end,
            }
            self._available = True
        except aiohttp.ClientError as exception:
            _LOGGER.warning(exception)
            self._available = False
            return False
        return True


class OVOEnergyLastGasReading(OVOEnergySensor):
    """Defines a OVO Energy card count sensor."""

    def __init__(self, client):
        """Initialize OVO Energy sensor."""

        super().__init__(
            client,
            f"{DOMAIN}_{client.account_id}_last_gas_reading",
            "OVO Last Gas Reading",
            "mdi:gas-cylinder",
            "kWh",
        )

    async def _ovo_energy_update(self) -> bool:
        """Update OVO Energy entity."""
        now = datetime.utcnow()
        try:
            usage: OVODailyUsage = await self._client.get_daily_usage(
                now.strftime("%Y-%m")
            )
            if usage is None or usage.gas is None:
                _LOGGER.warning("No data found for %s", self._name)
                self._available = False
            last_reading: OVODailyGas = usage.gas[len(usage.gas) - 1]
            self._state = last_reading.consumption
            self._attributes = {
                "start_time": last_reading.interval.start,
                "end_time": last_reading.interval.end,
            }
            self._available = True
        except aiohttp.ClientError as exception:
            _LOGGER.warning(exception)
            self._available = False
            return False
        return True
