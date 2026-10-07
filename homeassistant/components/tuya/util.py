"""Utility methods for the Tuya integration."""

from tuya_device_handlers import TUYA_QUIRKS_REGISTRY
from tuya_sharing import CustomerDevice

from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CELSIUS_ALIASES, DOMAIN, FAHRENHEIT_ALIASES, DPCode


def _parse_reported_temperature_unit(raw: object) -> UnitOfTemperature | None:
    """Map a Tuya unit token to a Home Assistant temperature unit."""
    if not isinstance(raw, str):
        return None
    token = raw.strip().lower()
    if token in CELSIUS_ALIASES:
        return UnitOfTemperature.CELSIUS
    if token in FAHRENHEIT_ALIASES:
        return UnitOfTemperature.FAHRENHEIT
    return None


def get_temperature_unit(
    device: CustomerDevice, dpcode_uom: str | None
) -> UnitOfTemperature | None:
    """Convert the DPCode unit of measurement to a temperature unit."""
    if not dpcode_uom:
        return get_device_temp_unit_convert(device)

    return _parse_reported_temperature_unit(dpcode_uom)


def get_device_temp_unit_convert(device: CustomerDevice) -> UnitOfTemperature | None:
    """Return the live temperature unit from c_f or temp_unit_convert.

    ``c_f`` is checked first, matching the historical Tuya climate behavior.
    Unrecognised values are ignored so a later datapoint can still match.
    """
    for dp_code in (DPCode.C_F, DPCode.TEMP_UNIT_CONVERT):
        if (raw := device.status.get(dp_code)) is None:
            continue
        if (unit := _parse_reported_temperature_unit(raw)) is not None:
            return unit
    return None


class ActionDPCodeNotFoundError(ServiceValidationError):
    """Custom exception for action DP code not found errors."""

    def __init__(
        self, device: CustomerDevice, expected: str | tuple[str, ...] | None
    ) -> None:
        """Initialize the error with device and expected DP codes."""
        if expected is None:
            expected = ()  # empty tuple for no expected codes
        elif not isinstance(expected, tuple):
            expected = (expected,)

        super().__init__(
            translation_domain=DOMAIN,
            translation_key="action_dpcode_not_found",
            translation_placeholders={
                "expected": str(
                    sorted(
                        [dp.value if isinstance(dp, DPCode) else dp for dp in expected]
                    )
                ),
                "available": str(sorted(device.function.keys())),
            },
        )


def get_device_info(device: CustomerDevice) -> DeviceInfo:
    """Get device info."""
    manufacturer = "Tuya"
    model: str | None = device.product_name
    model_id: str | None = device.product_id

    if (
        quirk := TUYA_QUIRKS_REGISTRY.get_quirk_for_device(device)
    ) and quirk.manufacturer:
        # If the manufacturer is not set, we cannot trust the model/model_id
        manufacturer = quirk.manufacturer
        model = quirk.model
        model_id = quirk.model_id

    return DeviceInfo(
        identifiers={(DOMAIN, device.id)},
        manufacturer=manufacturer,
        name=device.name,
        model=model,
        model_id=model_id,
    )
