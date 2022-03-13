"""Remote vehicle services for Subaru integration."""
import logging

from subarulink.exceptions import SubaruException

from homeassistant.exceptions import HomeAssistantError

from .const import SERVICE_UNLOCK, VEHICLE_NAME, VEHICLE_VIN

_LOGGER = logging.getLogger(__name__)


async def async_call_remote_service(controller, cmd, vehicle_info, arg=None):
    """Execute subarulink remote command."""
    car_name = vehicle_info[VEHICLE_NAME]
    vin = vehicle_info[VEHICLE_VIN]

    _LOGGER.debug("Sending %s command command to %s", cmd, car_name)
    success = False
    err_msg = ""
    try:
        if cmd == SERVICE_UNLOCK:
            success = await getattr(controller, cmd)(vin, arg)
        else:
            success = await getattr(controller, cmd)(vin)
    except SubaruException as err:
        err_msg = err.message

    if success:
        _LOGGER.debug("%s command successfully completed for %s", cmd, car_name)
        return

    raise HomeAssistantError(f"Service {cmd} failed for {car_name}: {err_msg}")
