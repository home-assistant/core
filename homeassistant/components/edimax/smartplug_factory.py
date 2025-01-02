"""Factory and mocking instance of Editmax SmartPlug for testing purposes."""

from pyedimax.smartplug import SmartPlug

from homeassistant.core import HomeAssistant


class SmartPlugFactory:
    """Class Factory for SmartPlug."""

    @staticmethod
    def create_plug_Instance(host: str, auth=("", "")) -> SmartPlug:
        """Create instance of SmartPlug or moked smart plug."""

        return SmartPlug(host, auth)

    @staticmethod
    async def async_create_smart_plug(
        hass: HomeAssistant, host, auth=("username", "password")
    ) -> SmartPlug:
        """Create SmartPlug or MockedSmartPlug instance for easier debugging."""

        return await hass.async_add_executor_job(
            SmartPlugFactory.create_plug_Instance, host, auth
        )
