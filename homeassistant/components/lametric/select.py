"""Support for LaMetric selects."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from demetriek import (
    BrightnessMode,
    Device,
    DisplayScreensaverModes,
    DisplayScreensaverScreenOff,
    DisplayScreensaverTimeBased,
    DisplayScreensaverWhenDark,
    LaMetricDevice,
    ScreensaverMode,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMetricConfigEntry, LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity
from .helpers import lametric_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LaMetricSelectEntityDescription(SelectEntityDescription):
    """Class describing LaMetric select entities."""

    current_fn: Callable[[Device], str]
    select_fn: Callable[[LaMetricDevice, str], Awaitable[Any]]


SELECTS = [
    LaMetricSelectEntityDescription(
        key="brightness_mode",
        translation_key="brightness_mode",
        entity_category=EntityCategory.CONFIG,
        options=["auto", "manual"],
        current_fn=lambda device: device.display.brightness_mode.value,
        select_fn=lambda api, opt: api.display(brightness_mode=BrightnessMode(opt)),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMetricConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LaMetric select based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        LaMetricSelectEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in SELECTS
    )

    # Like its schedule, the SKY is not known to support the screensaver.
    screensaver = coordinator.data.display.screensaver
    if coordinator.data.model != "sa5" and screensaver and screensaver.modes:
        async_add_entities([LaMetricScreensaverModeSelect(coordinator)])


class LaMetricSelectEntity(LaMetricEntity, SelectEntity):
    """Representation of a LaMetric select."""

    entity_description: LaMetricSelectEntityDescription

    def __init__(
        self,
        coordinator: LaMetricDataUpdateCoordinator,
        description: LaMetricSelectEntityDescription,
    ) -> None:
        """Initiate LaMetric Select."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}-{description.key}"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.current_fn(self.coordinator.data)

    @lametric_exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.coordinator.lametric, option)
        await self.coordinator.async_request_refresh()


class LaMetricScreensaverModeSelect(LaMetricEntity, SelectEntity):
    """Representation of the LaMetric screensaver mode select.

    The device always has exactly one screensaver mode active; switching
    another one on switches the active one off.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "screensaver_mode"

    def __init__(self, coordinator: LaMetricDataUpdateCoordinator) -> None:
        """Initiate the LaMetric screensaver mode select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data.serial_number}-screensaver_mode"

    @property
    def _modes(self) -> DisplayScreensaverModes:
        """Return the screensaver modes of the device."""
        screensaver = self.coordinator.data.display.screensaver
        if TYPE_CHECKING:
            assert screensaver is not None
            assert screensaver.modes is not None
        return screensaver.modes

    @property
    def _mode_states(
        self,
    ) -> dict[
        ScreensaverMode,
        DisplayScreensaverScreenOff
        | DisplayScreensaverTimeBased
        | DisplayScreensaverWhenDark
        | None,
    ]:
        """Return the state of each screensaver mode, None when not reported."""
        modes = self._modes
        return {
            ScreensaverMode.SCREEN_OFF: modes.screen_off,
            ScreensaverMode.TIME_BASED: modes.time_based,
            ScreensaverMode.WHEN_DARK: modes.when_dark,
        }

    @property
    @override
    def options(self) -> list[str]:
        """Return the screensaver modes the device reports."""
        return [
            mode.value for mode, state in self._mode_states.items() if state is not None
        ]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the active screensaver mode."""
        for mode, state in self._mode_states.items():
            if state is not None and state.enabled:
                return mode.value
        return None

    @lametric_exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Switch to another screensaver mode."""
        mode = ScreensaverMode(option)
        if mode is not ScreensaverMode.TIME_BASED:
            await self.coordinator.lametric.display(
                screensaver_mode=mode, screensaver_mode_enabled=True
            )
            await self.coordinator.async_request_refresh()
            return

        # The device only takes the time based mode together with its times.
        time_based = self._modes.time_based
        if time_based.start_time is None or time_based.end_time is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="screensaver_times_required",
            )

        await self.coordinator.lametric.display(
            screensaver_mode=mode,
            screensaver_mode_enabled=True,
            screensaver_start_time=time_based.start_time,
            screensaver_end_time=time_based.end_time,
        )
        await self.coordinator.async_request_refresh()
