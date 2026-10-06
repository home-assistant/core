"""Platform for button integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from boschshcpy import SHCSmokeDetector
from boschshcpy.device import SHCDevice

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SHCButtonEntityDescription[_DeviceT: SHCDevice](ButtonEntityDescription):
    """Describes a SHC button entity."""

    press_fn: Callable[[_DeviceT], None]


SMOKE_TEST_DESCRIPTION = SHCButtonEntityDescription[SHCSmokeDetector](
    key="smoke_test",
    translation_key="smoke_test",
    entity_category=EntityCategory.DIAGNOSTIC,
    press_fn=lambda device: device.smoketest_requested(),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC button platform."""
    session = config_entry.runtime_data

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    async_add_entities(
        SHCButton(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SMOKE_TEST_DESCRIPTION,
        )
        for device in session.device_helper.smoke_detectors
    )


class SHCButton[_DeviceT: SHCDevice](SHCEntity, ButtonEntity):
    """Generic SHC button entity, driven by a SHCButtonEntityDescription."""

    entity_description: SHCButtonEntityDescription[_DeviceT]
    _device: _DeviceT

    def __init__(
        self,
        hass: HomeAssistant,
        device: _DeviceT,
        parent_id: str,
        entry_id: str,
        description: SHCButtonEntityDescription[_DeviceT],
    ) -> None:
        """Initialize the button entity."""
        self.entity_description = description
        super().__init__(
            hass=hass, device=device, parent_id=parent_id, entry_id=entry_id
        )
        self._attr_unique_id = f"{device.serial}_{description.key}"

    @override
    def press(self) -> None:
        """Press the button."""
        self.entity_description.press_fn(self._device)
