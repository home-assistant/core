"""Support for MELCloud device numbers."""

from collections.abc import Awaitable, Callable
import dataclasses
from typing import override

from aiohttp import ClientError
from pymelcloud import DEVICE_TYPE_ATW
from pymelcloud.atw_device import (
    ZONE_OPERATION_MODE_COOL_FLOW,
    ZONE_OPERATION_MODE_HEAT_FLOW,
    Zone,
)

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import MelCloudConfigEntry, MelCloudDeviceUpdateCoordinator
from .entity import AtwZoneEntity

FLOW_MODES = {ZONE_OPERATION_MODE_HEAT_FLOW, ZONE_OPERATION_MODE_COOL_FLOW}


@dataclasses.dataclass(frozen=True, kw_only=True)
class MelcloudNumberEntityDescription(NumberEntityDescription):
    """Describes a MELCloud number entity."""

    value_fn: Callable[[Zone], float | None]
    set_fn: Callable[[Zone, float], Awaitable[None]]
    available_fn: Callable[[Zone], bool]
    min_value_fn: Callable[[Zone], float]
    max_value_fn: Callable[[Zone], float]


ATW_ZONE_NUMBERS: tuple[MelcloudNumberEntityDescription, ...] = (
    MelcloudNumberEntityDescription(
        key="flow_temperature",
        translation_key="flow_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda zone: zone.target_flow_temperature,
        set_fn=lambda zone, value: zone.set_target_flow_temperature(value),
        available_fn=lambda zone: zone.operation_mode in FLOW_MODES,
        min_value_fn=lambda zone: (
            5 if zone.operation_mode == ZONE_OPERATION_MODE_COOL_FLOW else 25
        ),
        max_value_fn=lambda zone: (
            25 if zone.operation_mode == ZONE_OPERATION_MODE_COOL_FLOW else 60
        ),
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: MelCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud numbers based on config_entry."""
    coordinators = entry.runtime_data
    async_add_entities(
        AtwZoneNumber(coordinator, zone, description)
        for coordinator in coordinators.get(DEVICE_TYPE_ATW, [])
        for zone in coordinator.device.zones
        for description in ATW_ZONE_NUMBERS
    )


class AtwZoneNumber(AtwZoneEntity, NumberEntity):
    """Number entity for an Air-to-Water zone."""

    entity_description: MelcloudNumberEntityDescription

    def __init__(
        self,
        coordinator: MelCloudDeviceUpdateCoordinator,
        zone: Zone,
        description: MelcloudNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, zone)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.serial}-{zone.zone_index}-{description.key}"
        )
        self._attr_native_step = coordinator.device.temperature_increment

    @property
    @override
    def available(self) -> bool:
        """Return True while the setting applies to the zone's current mode."""
        return super().available and self.entity_description.available_fn(self._zone)

    @property
    @override
    def native_min_value(self) -> float:
        """Return the minimum settable value."""
        return self.entity_description.min_value_fn(self._zone)

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum settable value."""
        return self.entity_description.max_value_fn(self._zone)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self._zone)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        try:
            await self.entity_description.set_fn(self._zone, value)
        except ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_number_failed",
            ) from err
        await self.coordinator.async_request_refresh()
