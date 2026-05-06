"""Utility methods for the Tuya integration."""

from tuya_sharing import CustomerDevice

from homeassistant.exceptions import ServiceValidationError

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
