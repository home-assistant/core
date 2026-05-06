"""Utility methods for the Tuya integration."""

from tuya_sharing import CustomerDevice

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, DPCode


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


def get_device_info(device: CustomerDevice, *, initial: bool = False) -> DeviceInfo:
    """Get device info."""
    manufacturer = "Tuya"
    model = device.product_name
    model_id = device.product_id

    if initial:
        # Note: the model is overridden via entity.device_info property
        # when the entity is created. If no entities are generated, it will
        # stay as unsupported
        model = f"{device.product_name} (unsupported)"

    return DeviceInfo(
        identifiers={(DOMAIN, device.id)},
        manufacturer=manufacturer,
        name=device.name,
        model=model,
        model_id=model_id,
    )
