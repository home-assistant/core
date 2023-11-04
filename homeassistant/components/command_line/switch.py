"""Support for custom shell commands to turn a switch on/off."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COMMAND_STATE,
    CONF_ICON,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import ManualTriggerEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, slugify

from .const import CONF_COMMAND_TIMEOUT, LOGGER
from .utils import call_shell_with_timeout, check_output_or_log

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Find and return switches controlled by shell commands."""

    discovery_info = cast(DiscoveryInfoType, discovery_info)
    entities: dict[str, Any] = {slugify(discovery_info[CONF_NAME]): discovery_info}

    switches = []

    for object_id, device_config in entities.items():
        trigger_entity_config = {
            CONF_UNIQUE_ID: device_config.get(CONF_UNIQUE_ID),
            CONF_NAME: Template(device_config.get(CONF_NAME, object_id), hass),
            CONF_ICON: device_config.get(CONF_ICON),
        }

        value_template: Template | None = device_config.get(CONF_VALUE_TEMPLATE)

        if value_template is not None:
            value_template.hass = hass

        switches.append(
            CommandSwitch(
                trigger_entity_config,
                object_id,
                device_config[CONF_COMMAND_ON],
                device_config[CONF_COMMAND_OFF],
                device_config.get(CONF_COMMAND_STATE),
                value_template,
                device_config[CONF_COMMAND_TIMEOUT],
                device_config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL),
            )
        )

    async_add_entities(switches)


class CommandSwitch(ManualTriggerEntity, SwitchEntity):
    """Representation a switch that can be toggled using shell commands."""

    _attr_should_poll = False

    def __init__(
        self,
        config: ConfigType,
        object_id: str,
        command_on: str,
        command_off: str,
        command_state: str | None,
        value_template: Template | None,
        timeout: int,
        scan_interval: timedelta,
    ) -> None:
        """Initialize the switch."""
        super().__init__(self.hass, config)
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._attr_is_on = False
        self._command_on = command_on
        self._command_off = command_off
        self._command_state = command_state
        self._value_template = value_template
        self._timeout = timeout
        self._scan_interval = scan_interval
        self._process_updates: asyncio.Lock | None = None

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        if self._command_state:
            self.async_on_remove(
                async_track_time_interval(
                    self.hass,
                    self._update_entity_state,
                    self._scan_interval,
                    name=f"Command Line Cover - {self.name}",
                    cancel_on_shutdown=True,
                ),
            )

    async def _switch(self, command: str) -> bool:
        """Execute the actual commands."""
        LOGGER.info("Running command: %s", command)

        success = (
            await self.hass.async_add_executor_job(
                call_shell_with_timeout, command, self._timeout
            )
            == 0
        )

        if not success:
            LOGGER.error("Command failed: %s", command)

        return success

    def _query_state_value(self, command: str) -> str | None:
        """Execute state command for return value."""
        LOGGER.info("Running state value command: %s", command)
        return check_output_or_log(command, self._timeout)

    def _query_state_code(self, command: str) -> bool:
        """Execute state command for return code."""
        LOGGER.info("Running state code command: %s", command)
        return (
            call_shell_with_timeout(command, self._timeout, log_return_code=False) == 0
        )

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._command_state is None

    def _query_state(self) -> str | int | None:
        """Query for state."""
        if self._command_state:
            if self._value_template:
                return self._query_state_value(self._command_state)
            return self._query_state_code(self._command_state)
        if TYPE_CHECKING:
            return None

    async def _update_entity_state(self, now) -> None:
        """Update the state of the entity."""
        if self._process_updates is None:
            self._process_updates = asyncio.Lock()
        if self._process_updates.locked():
            LOGGER.warning(
                "Updating Command Line Switch %s took longer than the scheduled update interval %s",
                self.name,
                self._scan_interval,
            )
            return

        async with self._process_updates:
            await self._async_update()

    async def _async_update(self) -> None:
        """Update device state."""
        if self._command_state:
            payload = str(await self.hass.async_add_executor_job(self._query_state))
            value = None
            if self._value_template:
                value = self._value_template.async_render_with_possible_json_value(
                    payload, None
                )
            self._attr_is_on = None
            if payload or value:
                self._attr_is_on = (value or payload).lower() == "true"
            self._process_manual_data(payload)
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._update_entity_state(dt_util.now())

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if await self._switch(self._command_on) and not self._command_state:
            self._attr_is_on = True
            self.async_schedule_update_ha_state()
        await self._update_entity_state(None)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if await self._switch(self._command_off) and not self._command_state:
            self._attr_is_on = False
            self.async_schedule_update_ha_state()
        await self._update_entity_state(None)
