"""Cosa class for interacting with the Cosa API."""

from .api import Api


class CosaManager:
    """Class for interacting with the Cosa API."""

    __username = None
    __password = None
    __api = None

    def __init__(self, username: str, password: str) -> None:
        """Initialize the Cosa instance with username and password."""
        self.__username = username
        self.__password = password
        self.__api = Api(self.__username, self.__password)

    async def getConnectionStatus(self) -> bool:
        """Check if the Cosa API connection is working."""
        return await self.__api.async_connection_status()

    __homeId = None

    def getHomeId(self) -> str | None:
        """Retrieve the home ID from the API."""
        if self.__homeId is not None:
            return self.__homeId

        endpoints = self.__api.async_get_endpoints()
        if endpoints is None:
            return None

        if endpoints == 0:
            return None

        return endpoints[0]["id"]

    def getCurrentStatus(self) -> dict | None:
        """Retrieve the current status from the API."""
        homeId = self.getHomeId()
        if homeId is None:
            return None

        return self.__api.async_get_endpoint(homeId)

    def setTemperature(self, targetTemp: int) -> bool:
        """Set the target temperature for the device.

        Args:
            targetTemp (int): The desired target temperature.

        Returns:
            bool: True if the temperature was successfully set, False otherwise.

        """
        homeId = self.getHomeId()
        if homeId is None:
            return False

        currentStatus = self.__api.async_get_endpoint(homeId)
        if currentStatus is None:
            return False

        homeTemp = currentStatus["homeTemperature"]
        awayTemp = currentStatus["awayTemperature"]
        sleepTemp = currentStatus["sleepTemperature"]
        customTemp = currentStatus["customTemperature"]

        currentMode = currentStatus["mode"]
        currentOption = currentStatus["option"]

        if (
            currentMode == "manual"
            and currentOption == "custom"
            and customTemp == targetTemp
        ):
            # already set to targetTemp
            return True

        targetSetSuccess = self.__api.async_set_target_temperatures(
            homeId, homeTemp, awayTemp, sleepTemp, targetTemp
        )
        if not targetSetSuccess:
            return False

        if currentMode == "manual" and currentOption == "custom":
            # already set to manual mode
            return True

        modeSetSuccess = self.__api.async_enable_custom_mode(homeId)
        if not modeSetSuccess:
            # try revert back to previous temperature. If this fails, then it's a lost cause
            self.__api.async_set_target_temperatures(
                homeId, homeTemp, awayTemp, sleepTemp, customTemp
            )
            return False

        return True

    def turnOff(self) -> bool:
        """Turn off the device by setting it to 'frozen' mode."""
        homeId = self.getHomeId()
        if homeId is None:
            return False

        currentStatus = self.__api.async_get_endpoint(homeId)
        if currentStatus is None:
            return False

        currentMode = currentStatus["mode"]
        currentOption = currentStatus["option"]

        if currentMode == "manual" and currentOption == "frozen":
            # already turned off
            return True

        return self.__api.async_disable(homeId)

    def enableSchedule(self) -> bool:
        """Enable the schedule mode on the device."""
        homeId = self.getHomeId()
        if homeId is None:
            return False

        currentStatus = self.__api.async_get_endpoint(homeId)
        if currentStatus is None:
            return False

        currentMode = currentStatus["mode"]

        if currentMode == "schedule":
            # already enabled
            return True

        return self.__api.async_enable_schedule(homeId)
