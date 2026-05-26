"""Number platform for HDFury Integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from hdfury import HDFuryAPI, HDFuryError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import HDFuryConfigEntry
from .entity import HDFuryEntity

PARALLEL_UPDATES = 1


@dataclass(kw_only=True, frozen=True)
class HDFuryNumberEntityDescription(NumberEntityDescription):
    """Description for HDFury number entities."""

    set_value_fn: Callable[[HDFuryAPI, str], Awaitable[None]]


NUMBERS: tuple[HDFuryNumberEntityDescription, ...] = (
    HDFuryNumberEntityDescription(
        key="unmutecnt",
        translation_key="audio_unmute",
        entity_registry_enabled_default=False,
        mode=NumberMode.BOX,
        native_min_value=50,
        native_max_value=1000,
        native_step=1,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_audio_unmute(value),
    ),
    HDFuryNumberEntityDescription(
        key="earcunmutecnt",
        translation_key="earc_unmute",
        entity_registry_enabled_default=False,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=1000,
        native_step=1,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_earc_unmute(value),
    ),
    HDFuryNumberEntityDescription(
        key="oledfade",
        translation_key="oled_fade",
        mode=NumberMode.BOX,
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_oled_fade(value),
    ),
    HDFuryNumberEntityDescription(
        key="reboottimer",
        translation_key="reboot_timer",
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_reboot_timer(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HDFuryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers using the platform schema."""

    runtime_data = entry.runtime_data
    coordinator = runtime_data.config_coordinator

    async_add_entities(
        HDFuryNumber(coordinator, runtime_data, description)
        for description in NUMBERS
        if description.key in coordinator.data
    )


class HDFuryNumber(HDFuryEntity, NumberEntity):
    """Base HDFury Number Class."""

    entity_description: HDFuryNumberEntityDescription

    @property
    def native_value(self) -> float:
        """Return the current number value."""

        return float(self.coordinator.data[self.entity_description.key])

    async def async_set_native_value(self, value: float) -> None:
        """Set Number Value Event."""

        try:
            await self.entity_description.set_value_fn(
                self.runtime_data.client, str(int(value))
            )
        except HDFuryError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

        self.coordinator.data[self.entity_description.key] = str(int(value))
        self.coordinator.async_set_updated_data(self.coordinator.data)
