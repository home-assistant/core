"""The output limit which can be set in the APsystems local API integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiohttp import ClientConnectorError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .coordinator import (
    ApSystemsConfigEntry,
    ApSystemsData,
    Lake6Coordinator,
    Lake6Data,
    Lake6RuntimeData,
)
from .entity import ApSystemsEntity, Lake6Entity
from .lake6.const import (
    LAKE6_DEPTH_OF_DISCHARGE_MAX,
    LAKE6_DEPTH_OF_DISCHARGE_MIN,
    LAKE6_DEPTH_OF_DISCHARGE_STEP,
    LAKE6_MANUAL_DURATION_MAX,
    LAKE6_MANUAL_DURATION_MIN,
    LAKE6_MANUAL_DURATION_STEP,
    LAKE6_MANUAL_POWER_MAX,
    LAKE6_MANUAL_POWER_MIN,
    LAKE6_MANUAL_POWER_MODES,
    LAKE6_MANUAL_POWER_STEP,
    LAKE6_MODE_ATTR_TO_FIELD,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ApSystemsConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    if isinstance(config_entry.runtime_data, Lake6RuntimeData):
        coordinator = config_entry.runtime_data.coordinator
        add_entities(
            [
                *(
                    Lake6NumberEntity(coordinator, description)
                    for description in LAKE6_NUMBERS
                ),
                Lake6ManualPowerNumber(coordinator),
                Lake6ManualDurationNumber(coordinator),
            ]
        )
        return

    add_entities([ApSystemsMaxOutputNumber(config_entry.runtime_data)], True)


class ApSystemsMaxOutputNumber(ApSystemsEntity, NumberEntity):
    """Base sensor to be used with description."""

    _attr_native_step = 1
    _attr_device_class = NumberDeviceClass.POWER
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_translation_key = "max_output"

    def __init__(
        self,
        data: ApSystemsData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data)
        self._api = data.coordinator.api
        self._attr_unique_id = f"{data.device_id}_output_limit"
        self._attr_native_max_value = data.coordinator.api.max_power
        self._attr_native_min_value = data.coordinator.api.min_power

    async def async_update(self) -> None:
        """Set the state with the value fetched from the inverter."""
        try:
            status = await self._api.get_max_power()
        except TimeoutError, ClientConnectorError:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_native_value = status

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the desired output power."""
        self._attr_native_value = await self._api.set_max_power(int(value))


@dataclass(frozen=True, kw_only=True)
class Lake6NumberEntityDescription(NumberEntityDescription):
    """Describes a Lake_6 writable parameter."""

    value_fn: Callable[[Lake6Data], int | None]


LAKE6_NUMBERS: tuple[Lake6NumberEntityDescription, ...] = (
    # The device field dod means the lowest state of charge the battery may
    # discharge to in backup mode, which the product calls backupSoc. A larger
    # value is more conservative, so the name must be Backup SOC rather than
    # Depth of Discharge.
    Lake6NumberEntityDescription(
        key="depth_of_discharge",
        translation_key="depth_of_discharge",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=LAKE6_DEPTH_OF_DISCHARGE_MIN,
        native_max_value=LAKE6_DEPTH_OF_DISCHARGE_MAX,
        native_step=LAKE6_DEPTH_OF_DISCHARGE_STEP,
        mode=NumberMode.BOX,
        value_fn=lambda d: d.modes.depth_of_discharge,
    ),
)


class Lake6NumberEntity(Lake6Entity, NumberEntity):
    """A writable Lake_6 parameter backed by one `/modes` field."""

    entity_description: Lake6NumberEntityDescription

    def __init__(
        self,
        coordinator: Lake6Coordinator,
        entity_description: Lake6NumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self.device_id}_{entity_description.key}"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value read from `/modes`."""
        return self.entity_description.value_fn(self.coordinator.data)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write one field."""
        # The device only accepts strings here, and these fields are integers.
        field = LAKE6_MODE_ATTR_TO_FIELD[self.entity_description.key]
        target = int(value)
        await self.coordinator.async_set_modes(**{field: str(target)})


class Lake6ManualPowerNumber(Lake6Entity, NumberEntity):
    """Wattage of the immediate manual control request.

    The value is staged, not written: the request is sent only when the
    dispatch button is pressed.
    """

    _attr_translation_key = "manual_control_power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = LAKE6_MANUAL_POWER_MIN
    _attr_native_max_value = LAKE6_MANUAL_POWER_MAX
    _attr_native_step = LAKE6_MANUAL_POWER_STEP
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: Lake6Coordinator) -> None:
        """Initialize the manual control power box."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device_id}_manual_control_power"

    @property
    @override
    def available(self) -> bool:
        """Only offer wattage where it takes part in the request.

        Standby always sends `power "0"` (§4.7) and a blank form after an
        interrupt has nothing to send, so the box hides in both cases; only
        charge and discharge consume a wattage. A `!= standby` check would
        keep it visible after `reset` left the mode `None`.
        """
        if not super().available:
            return False
        return self.coordinator.manual_control.mode in LAKE6_MANUAL_POWER_MODES

    @property
    @override
    def native_value(self) -> float | None:
        """Return the staged wattage."""
        return self.coordinator.manual_control.power

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Stage the wattage."""
        await self.coordinator.async_set_manual_control(power=int(value))


class Lake6ManualDurationNumber(Lake6Entity, NumberEntity):
    """How long the immediate manual control request should last."""

    _attr_translation_key = "manual_control_duration"
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = LAKE6_MANUAL_DURATION_MIN
    _attr_native_max_value = LAKE6_MANUAL_DURATION_MAX
    _attr_native_step = LAKE6_MANUAL_DURATION_STEP
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: Lake6Coordinator) -> None:
        """Initialize the manual control duration box."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device_id}_manual_control_duration"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the staged duration."""
        return self.coordinator.manual_control.duration

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Stage the duration."""
        await self.coordinator.async_set_manual_control(duration=int(value))
