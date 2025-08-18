"""Support for Hinen Sensors."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AUTH, CD_PERIOD_TIMES2, COORDINATOR, DOMAIN
from .coordinator import HinenDataUpdateCoordinator
from .entity import HinenDeviceEntity
from .hinen import HinenOpen

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=False)
class HinenNumberEntityDescription(NumberEntityDescription):
    """Describes Hinen number entity."""


@dataclass(frozen=True, kw_only=False)
class HinenCDPeriodTimesEntityDescription(NumberEntityDescription):
    """Describes Hinen CD Period Times entity."""

    period_index: int = 0
    property_key: str = ""


NUMBER_TYPES = [
    HinenNumberEntityDescription(
        key="load_first_stop_soc",
        translation_key="load_first_stop_soc",
        entity_category=EntityCategory.CONFIG,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    HinenNumberEntityDescription(
        key="charge_stop_soc",
        translation_key="charge_stop_soc",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    HinenNumberEntityDescription(
        key="grid_first_stop_soc",
        translation_key="grid_first_stop_soc",
        entity_category=EntityCategory.CONFIG,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
]

# Generate CD Period Times entity descriptions for 0-6 periods
CD_PERIOD_TIMES_TYPES = []
for period_index in range(6):  # 0-5 periods
    # Period Start
    CD_PERIOD_TIMES_TYPES.append(
        HinenCDPeriodTimesEntityDescription(
            key=f"cd_period_times_{period_index + 1}_start",
            translation_key=f"cd_period_times_{period_index + 1}_start",
            entity_category=EntityCategory.CONFIG,
            native_min_value=0,
            native_max_value=1440,
            native_step=1,
            period_index=period_index,
            property_key="periodTimeStart",
            native_unit_of_measurement="Minutes",
        )
    )
    # Period Rate
    CD_PERIOD_TIMES_TYPES.append(
        HinenCDPeriodTimesEntityDescription(
            key=f"cd_period_times_{period_index + 1}_rate",
            translation_key=f"cd_period_times_{period_index + 1}_rate",
            entity_category=EntityCategory.CONFIG,
            native_min_value=-100,
            native_max_value=100,
            native_step=1,
            period_index=period_index,
            property_key="periodTimeRate",
            native_unit_of_measurement=PERCENTAGE,
        )
    )
    # Period End
    CD_PERIOD_TIMES_TYPES.append(
        HinenCDPeriodTimesEntityDescription(
            key=f"cd_period_times_{period_index + 1}_end",
            translation_key=f"cd_period_times_{period_index + 1}_end",
            entity_category=EntityCategory.CONFIG,
            native_min_value=0,
            native_max_value=1440,
            native_step=1,
            period_index=period_index,
            property_key="periodTimeEnd",
            native_unit_of_measurement="Minutes",
        )
    )
    # Period Stop SOC
    CD_PERIOD_TIMES_TYPES.append(
        HinenCDPeriodTimesEntityDescription(
            key=f"cd_period_times_{period_index + 1}_stop_soc",
            translation_key=f"cd_period_times_{period_index + 1}_stop_soc",
            entity_category=EntityCategory.CONFIG,
            native_min_value=0,
            native_max_value=100,
            native_step=1,
            period_index=period_index,
            property_key="periodTimeStopSoc",
            native_unit_of_measurement=PERCENTAGE,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hinen number."""
    coordinator: HinenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    hinen_open: HinenOpen = hass.data[DOMAIN][entry.entry_id][AUTH].hinen_open

    entities: list = [
        HinenNumber(coordinator, hinen_open, number_type, device_id)
        for device_id in coordinator.data
        for number_type in NUMBER_TYPES
    ]

    entities.extend(
        [
            HinenCDPeriodTimesNumber(coordinator, hinen_open, number_type, device_id)
            for device_id in coordinator.data
            for number_type in CD_PERIOD_TIMES_TYPES
        ]
    )

    async_add_entities(entities)


class HinenNumber(HinenDeviceEntity, NumberEntity):
    """Representation of a Hinen load first stop SOC number."""

    entity_description: HinenNumberEntityDescription

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return True

    @property
    def native_value(self) -> int | None:
        """Return the current load first stop SOC."""
        if not self.coordinator.data:
            return None
        attr_load_first_stop_soc = self.coordinator.data[self._device_id][
            self.entity_description.key
        ]
        _LOGGER.debug("current native_value: %s", attr_load_first_stop_soc)
        return attr_load_first_stop_soc

    async def async_set_native_value(self, value: float) -> None:
        """Set the current load first stop SOC."""
        _LOGGER.debug("set native_value: %s", value)
        if value is not None:
            await self.hinen_open.set_property(
                int(value), self._device_id, self.entity_description.key
            )
            self.coordinator.data[self._device_id][self.entity_description.key] = value
            self.async_write_ha_state()


class HinenCDPeriodTimesNumber(HinenDeviceEntity, NumberEntity):
    """Representation of a Hinen CD Period Times number."""

    entity_description: HinenCDPeriodTimesEntityDescription

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return True

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if not self.coordinator.data:
            return None

        # Get CDPeriodTimes2 data from coordinator
        cd_period_times = self.coordinator.data[self._device_id][CD_PERIOD_TIMES2]
        if (
            cd_period_times is None
            or len(cd_period_times) <= self.entity_description.period_index
        ):
            return None

        period_data = cd_period_times[self.entity_description.period_index]
        return float(period_data.get(self.entity_description.property_key, 0))

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        _LOGGER.debug(
            "Setting CD Period Times value: %s for key: %s",
            value,
            self.entity_description.key,
        )

        # Get current CDPeriodTimes2 data
        cd_period_times = self.coordinator.data[self._device_id][CD_PERIOD_TIMES2]
        if cd_period_times is None:
            # Initialize with default values if not exists
            cd_period_times = []

        # Update the specific period and property
        if len(cd_period_times) <= self.entity_description.period_index:
            # Extend the list if needed
            cd_period_times.extend(
                [
                    {
                        "periodEnable": 0,
                        "periodTimeStart": 0,
                        "periodTimeRate": 0,
                        "periodTimeEnd": 0,
                        "periodTimeStopSoc": 0,
                    }
                    for _ in range(
                        self.entity_description.period_index - len(cd_period_times) + 1
                    )
                ]
            )

        period_data = cd_period_times[self.entity_description.period_index]
        period_data[self.entity_description.property_key] = int(value)

        # Send update to device
        await self.hinen_open.set_property(
            cd_period_times, self._device_id, CD_PERIOD_TIMES2
        )

        # Update coordinator data
        self.coordinator.data[self._device_id][CD_PERIOD_TIMES2] = cd_period_times
        self.async_write_ha_state()
