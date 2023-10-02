"""Contain the base classes of entity descriptions."""

from enum import Enum
from logging import getLogger
from typing import Generic, TypeVar

from toshiba_ac.device import ToshibaAcDevice, ToshibaAcFeatures

_LOGGER = getLogger(__name__)
TEnum = TypeVar("TEnum", bound=Enum)


class ToshibaAcEnumEntityDescriptionMixin(Generic[TEnum]):
    """Mix in async_set_attr and get_attr helpers to dynamically set enum values."""

    ac_attr_name: str
    ac_attr_setter: str

    async def async_set_attr(
        self, device: ToshibaAcDevice, value: TEnum | None
    ) -> None:
        """Set the provided option enum value."""
        if not self.ac_attr_setter and not self.ac_attr_name:
            return
        if value is None:
            return
        setter = self.ac_attr_setter or f"set_{self.ac_attr_name}"
        _LOGGER.info("AC device %s calling %s %s", device.name, setter, value.name)
        await getattr(device, setter)(value)

    def get_device_attr(self, device: ToshibaAcDevice) -> TEnum | None:
        """Return the current option enum value."""
        if self.ac_attr_name:
            return getattr(device, self.ac_attr_name)
        return None

    def get_features_attr(self, features: ToshibaAcFeatures) -> list[TEnum]:
        """Return the supported enum values."""
        if self.ac_attr_name:
            return getattr(features, self.ac_attr_name)
        return []
