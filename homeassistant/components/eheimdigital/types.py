"""Types for EHEIM Digital."""

from typing import Literal, Protocol, overload

from eheimdigital.device import EheimDigitalDevice

from .entity import EheimDigitalEntity


class AsyncSetupDeviceEntitiesCallback(Protocol):
    """Callback to setup device entities."""

    @overload
    def __call__(
        self, device_address: str, *, return_entities: Literal[False]
    ) -> None: ...

    @overload
    def __call__(
        self, device_address: str, *, return_entities: Literal[True]
    ) -> list[EheimDigitalEntity[EheimDigitalDevice]]: ...

    def __call__(
        self, device_address: str, *, return_entities: bool
    ) -> None | list[EheimDigitalEntity[EheimDigitalDevice]]:
        """Set up EHEIM Digital device entities."""
