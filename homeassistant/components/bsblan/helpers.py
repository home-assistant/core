"""Helper functions for BSB-Lan integration."""

from bsblan import BSBLAN, BSBLANError, EntityInfo, StaticState

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN, Setpoint


def first_temperature(*sources: EntityInfo[float] | None) -> float | None:
    """Return the first usable temperature from the given sources."""
    for source in sources:
        if source is not None and source.value is not None:
            return source.value
    return None


def circuit_temperature_bounds(
    static: StaticState | None,
) -> tuple[float | None, float | None]:
    """Return the minimum and maximum setpoint of a heating circuit.

    Standard BSB/LPB circuits expose the bounds via heating_protective_setpoint
    (714) and comfort_setpoint_max (716); min_temp/max_temp (15006/15007) exist
    only on PPS devices. Inactive parameters ("---") have value None.
    """
    if static is None:
        return None, None
    return (
        first_temperature(static.heating_protective_setpoint, static.min_temp),
        first_temperature(static.comfort_setpoint_max, static.max_temp),
    )


def validate_setpoint_order(
    temperature: float,
    translation_key: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> None:
    """Raise if a setpoint would cross the setpoint it is paired with.

    The controller accepts a reduced setpoint above the comfort or nominal
    one, so the order is enforced here.
    """
    # Converting from Fahrenheit leaves float noise: 65.3 °F gives 18.499999 °C
    temperature = round(temperature, 2)
    if minimum is not None and temperature < minimum:
        limit = minimum
    elif maximum is not None and temperature > maximum:
        limit = maximum
    else:
        return
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=translation_key,
        translation_placeholders={"temperature": str(temperature), "limit": str(limit)},
    )


def setpoint_to_change(
    temperature: float,
    *,
    current: float | None,
    normal: float | None,
    reduced: float | None,
) -> Setpoint:
    """Return the setpoint a new target temperature changes.

    The reduced setpoint changes when it is the one in effect. When both
    setpoints are equal, either one could be in effect, so lowering changes
    the reduced one and raising the normal one to keep them in order.
    """
    if current is None or current != reduced:
        return Setpoint.NORMAL
    if current != normal or temperature < current:
        return Setpoint.REDUCED
    return Setpoint.NORMAL


async def async_sync_device_time(client: BSBLAN, device_name: str) -> None:
    """Synchronize BSB-LAN device time with Home Assistant.

    Only updates if device time differs from Home Assistant time.

    Args:
        client: The BSB-LAN client instance.
        device_name: The name of the device (used in error messages).

    Raises:
        HomeAssistantError: If the time sync operation fails.

    """
    try:
        device_time = await client.time()
        current_time = dt_util.now()
        current_time_str = current_time.strftime("%d.%m.%Y %H:%M:%S")

        # Only sync if device time differs from HA time
        if device_time.time.value != current_time_str:
            await client.set_time(current_time_str)
    except BSBLANError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="sync_time_failed",
            translation_placeholders={
                "device_name": device_name,
                "error": str(err),
            },
        ) from err
