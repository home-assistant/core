"""Detect underruns and capped status from the Raspberry Pi Kernel.

Minimal Kernel needed is 4.14+
"""

import asyncio
import contextlib
import logging
from typing import override

from rpi_bad_power import UnderVoltage

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    create_issue,
)

from . import RpiPowerConfigEntry
from .const import DOMAIN, ISSUE_UNDER_VOLTAGE

_LOGGER = logging.getLogger(__name__)

DESCRIPTION_NORMALIZED = "Voltage normalized. Everything is working as intended."
DESCRIPTION_UNDER_VOLTAGE = (
    "Under-voltage was detected. Consider getting an uninterruptible power supply for"
    " your Raspberry Pi."
)
PUSH_RETRY_INTERVAL = 30


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RpiPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up rpi_power binary sensor."""
    under_voltage = config_entry.runtime_data
    async_add_entities(
        [RaspberryChargerBinarySensor(under_voltage, config_entry)],
        update_before_add=True,
    )


class RaspberryChargerBinarySensor(BinarySensorEntity):
    """Binary sensor representing the rpi power status."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "rpi_power"
    _attr_has_entity_name = True
    # Legacy format, kept as migrating existing unique IDs is not worth the risk
    _attr_unique_id = "rpi_power"  # only one sensor possible  # pylint: disable=home-assistant-entity-unique-id-redundant-domain

    def __init__(
        self,
        under_voltage: UnderVoltage,
        config_entry: RpiPowerConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        self._under_voltage = under_voltage
        self._config_entry = config_entry
        self._attr_should_poll = not under_voltage.supports_push
        self._watch_task: asyncio.Task[None] | None = None

        self._attr_device_info = DeviceInfo(
            manufacturer="Raspberry Pi",
            identifiers={(DOMAIN, "rpi_power")},
            name="Raspberry Pi",
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Start kernel sysfs_notify watcher when push is supported."""
        await super().async_added_to_hass()
        if not self._under_voltage.supports_push:
            return
        self._watch_task = self._config_entry.async_create_background_task(
            self.hass,
            self._async_watch_under_voltage(),
            name="rpi_power_watch",
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel kernel watcher cleanly when entity is removed or unloaded."""
        if self._watch_task is not None:
            self._watch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watch_task
            self._watch_task = None
        await super().async_will_remove_from_hass()

    def _handle_error(self, err: OSError) -> bool:
        """Handle a sysfs read error; return True if availability changed."""
        if self._attr_available:
            _LOGGER.warning("Error reading under-voltage status: %s", err)
            self._attr_available = False
            return True
        return False

    def _apply_value(self, value: bool, *, from_event_loop: bool) -> bool:
        """Apply a new under-voltage reading; return True if state/availability changed."""
        changed = False
        if not self._attr_available:
            _LOGGER.info("Recovered reading under-voltage status")
            self._attr_available = True
            changed = True

        if self._attr_is_on != value:
            if value:
                _LOGGER.warning(DESCRIPTION_UNDER_VOLTAGE)
                issue_fn = async_create_issue if from_event_loop else create_issue
                issue_fn(
                    self.hass,
                    DOMAIN,
                    ISSUE_UNDER_VOLTAGE,
                    config_entry_id=self._config_entry.entry_id,
                    is_fixable=True,
                    is_persistent=True,
                    severity=IssueSeverity.CRITICAL,
                    translation_key=ISSUE_UNDER_VOLTAGE,
                )
            elif self._attr_is_on:
                _LOGGER.debug(DESCRIPTION_NORMALIZED)
            self._attr_is_on = value
            changed = True

        return changed

    async def _async_watch_under_voltage(self) -> None:
        """Watch kernel sysfs_notify events for under-voltage state changes."""
        while True:
            try:
                async with self._under_voltage.async_watch(
                    emit_initial=True
                ) as watcher:
                    async for value in watcher:
                        if self._apply_value(value, from_event_loop=True):
                            self.async_write_ha_state()
            except OSError as err:
                if self._handle_error(err):
                    self.async_write_ha_state()
            await asyncio.sleep(PUSH_RETRY_INTERVAL)

    def update(self) -> None:
        """Update the state synchronously (initial read and legacy polling fallback)."""
        if self._watch_task is not None:
            return
        try:
            value = self._under_voltage.get()
        except OSError as err:
            self._handle_error(err)
            return

        self._apply_value(value, from_event_loop=False)
