"""Actions for V2C chargers."""

from enum import StrEnum

import probatio
from pytrydan.exceptions import TrydanError

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .coordinator import V2CConfigEntry


class V2CService(StrEnum):
    """V2C actions."""

    SET_CONTRACTED_POWER = "set_contracted_power"


class V2CServiceArgument(StrEnum):
    """V2C action arguments."""

    POWER = "power"


SET_CONTRACTED_POWER_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): cv.string,
        probatio.Required(V2CServiceArgument.POWER): probatio.Coerce(int),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register V2C actions."""

    async def set_contracted_power(call: ServiceCall) -> None:
        """Set the device's overloaded contracted power parameter."""
        entry: V2CConfigEntry = service.async_get_device_and_config_entry(
            hass, DOMAIN, call.data[ATTR_DEVICE_ID]
        )[1]
        coordinator = entry.runtime_data
        try:
            await coordinator.evse.contracted_power(call.data[V2CServiceArgument.POWER])
        except TrydanError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_contracted_power_failed",
            ) from err
        finally:
            await coordinator.async_request_refresh()

    service.async_register_admin_service(
        hass,
        DOMAIN,
        V2CService.SET_CONTRACTED_POWER,
        set_contracted_power,
        SET_CONTRACTED_POWER_SCHEMA,
    )
