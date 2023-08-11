"""SpaNET Spa Water Heater.

- Retrieve the current and target temperature
- Sets the Target Temperature
- Retrieve the current operation mode
- Set operation mode
"""

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.components.water_heater import PLATFORM_SCHEMA, WaterHeaterEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DOMAIN,
    GET_OPERATION_MODE,
    GET_TARGET_TEMPERATURE,
    GET_TEMPERATURE,
    SET_OPERATION_MODE,
    SET_TEMPERATURE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required("name"): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up the spa water heater platform."""
    water_heater = Spa("", "", "")
    async_add_entities([water_heater])


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the spa entity."""
    access_token = str(entry.data.get("access_token"))
    refresh_token = str(entry.data.get("refresh_token"))
    name = str(entry.data.get("spa_name"))

    spa = Spa(name, access_token, refresh_token)
    async_add_entities([spa])


class Spa(WaterHeaterEntity):
    """SpaNET Spa water heater."""

    def __init__(self, name: str, access_token: str, refresh_token: str) -> None:
        """Initialize SpaNET Spa water heater."""
        self._name = name
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._current_temperature = 0.0
        self._target_temperature = 0.0
        self._is_away_mode_on = False
        self._operation_mode = ""

    @property
    def name(self) -> str:
        """Return the name of the spa."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the name of the spa water heater."""
        return f"{DOMAIN}_{self._name}"

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return self._target_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 10.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 41.8

    @property
    def is_away_mode_on(self) -> bool:
        """Return the status of AWAY MODE."""
        return self._is_away_mode_on

    @property
    def current_operation(self) -> str:
        """Return the current Operation Mode."""
        return self._operation_mode

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement for temperature."""
        return "°C"

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set the current Operation Mode - NORM, AWAY, WEEKEND."""
        await self.setOperationModeAPI(operation_mode)

    async def async_update(self) -> None:
        """Retrieve updated data by calling the API."""
        self._current_temperature = await self.getCurrentTemperatureAPI()
        self._target_temperature = await self.getTargetTemperatureAPI()

        self._operation_mode = await self.getOperationModeAPI()
        self._is_away_mode_on = self._operation_mode.lower() == "AWAY"

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set temperature of spa."""
        if "temperature" in kwargs:
            await self.setTemperatureAPI(int(kwargs["temperature"] * 10))

    async def getCurrentTemperatureAPI(self) -> float:
        """Retrieve current temperature."""
        headers = {"Authorization": f"Bearer {self._access_token}"}
        url = GET_TEMPERATURE
        try:
            async with aiohttp.ClientSession() as session, session.get(
                url, headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("temperature") / 10.0

                _LOGGER.error(
                    "Get Temperature failed with status code: %s",
                    response.status,
                )
                return 0.0

        except aiohttp.ClientError as err:
            _LOGGER.error("Error occurred during API call: %s", err)
            return 0.0

    async def getTargetTemperatureAPI(self) -> float:
        """Get target temperature."""
        headers = {"Authorization": f"Bearer {self._access_token}"}
        url = GET_TARGET_TEMPERATURE
        try:
            async with aiohttp.ClientSession() as session, session.get(
                url, headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("temperature") / 10.0

                _LOGGER.error(
                    "Get Temperature failed with status code: %s",
                    response.status,
                )
                return 0.0

        except aiohttp.ClientError as err:
            _LOGGER.error("Error occurred during API call: %s", err)
            return 0.0

    async def getOperationModeAPI(self) -> str:
        """Retrieve operation mode."""
        headers = {"Authorization": f"Bearer {self._access_token}"}
        url = GET_OPERATION_MODE
        try:
            async with aiohttp.ClientSession() as session, session.get(
                url, headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("mode")

                _LOGGER.error(
                    "Get Temperature failed with status code: %s",
                    response.status,
                )
                return ""

        except aiohttp.ClientError as err:
            _LOGGER.error("Error occurred during API call: %s", err)
            return ""

    async def setTemperatureAPI(self, temperature):
        """Set target temperature."""
        headers = {
            "Content-Type": "application/json",
        }
        payload = {"temperature": temperature}
        headers = {"Authorization": f"Bearer {self._access_token}"}
        url = SET_TEMPERATURE
        try:
            async with aiohttp.ClientSession() as session, session.post(
                url, json=payload, headers=headers
            ) as response:
                if response.status == 200:
                    _LOGGER.info("New temperature set successfully")
                    self._current_temperature = temperature
                    return True

                _LOGGER.error(
                    "Set Temperature failed with status code: %s",
                    response.status,
                )
                return False

        except aiohttp.ClientError as err:
            _LOGGER.error("Error occurred during API call: %s", err)
            return False

    async def setOperationModeAPI(self, operation_mode):
        """Set spa operation mode. Modes are: NORM, AWAY, WEEKEND."""
        headers = {
            "Content-Type": "application/json",
        }
        payload = {"mode": operation_mode}
        headers = {"Authorization": f"Bearer {self._access_token}"}
        url = SET_OPERATION_MODE
        try:
            async with aiohttp.ClientSession() as session, session.post(
                url, json=payload, headers=headers
            ) as response:
                if response.status == 200:
                    _LOGGER.info("New mode set successfully")
                    self._operation_mode = operation_mode
                    return True

                _LOGGER.error(
                    "Set Operation Mode failed with status code: %s",
                    response.status,
                )
                return False

        except aiohttp.ClientError as err:
            _LOGGER.error("Error occurred during API call: %s", err)
            return False
