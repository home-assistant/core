"""Support for command line covers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import CoverEntity
from homeassistant.const import (
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STATE,
    CONF_COMMAND_STOP,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import ManualTriggerEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, slugify

from .const import CONF_COMMAND_TIMEOUT, LOGGER, TRIGGER_ENTITY_OPTIONS
from .utils import async_call_shell_with_timeout, async_check_output_or_log

SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up cover controlled by shell commands."""
    if not discovery_info:
        return

    covers = []
    entities: dict[str, dict[str, Any]] = {
        slugify(discovery_info[CONF_NAME]): discovery_info
    }

    for device_name, cover_config in entities.items():
        trigger_entity_config = {
            CONF_NAME: Template(cover_config.get(CONF_NAME, device_name), hass),
            **{k: v for k, v in cover_config.items() if k in TRIGGER_ENTITY_OPTIONS},
        }

        covers.append(
            CommandCover(
                trigger_entity_config,
                cover_config[CONF_COMMAND_OPEN],
                cover_config[CONF_COMMAND_CLOSE],
                cover_config[CONF_COMMAND_STOP],
                cover_config.get(CONF_COMMAND_STATE),
                cover_config.get(CONF_VALUE_TEMPLATE),
                cover_config[CONF_COMMAND_TIMEOUT],
                cover_config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL),
            )
        )

    async_add_entities(covers)


class CommandCover(ManualTriggerEntity, CoverEntity):
    """Representation a command line cover."""

    _attr_should_poll = False

    def __init__(
        self,
        config: ConfigType,
        command_open: str,
        command_close: str,
        command_stop: str,
        command_state: str | None,
        value_template: Template | None,
        timeout: int,
        scan_interval: timedelta,
    ) -> None:
        """Initialize the cover."""
        super().__init__(self.hass, config)
        self._state: int | None = None
        self._command_open = command_open
        self._command_close = command_close
        self._command_stop = command_stop
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

    async def _async_move_cover(self, command: str) -> bool:
        """Execute the actual commands."""
        LOGGER.debug("Running command: %s", command)

        returncode = await async_call_shell_with_timeout(command, self._timeout)
        success = returncode == 0

        if not success:
            LOGGER.error(
                "Command failed (with return code %s): %s", returncode, command
            )

        return success

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self.current_cover_position is not None:
            return self.current_cover_position == 0
        return None

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._state

    async def _async_query_state(self) -> str | None:
        """Query for the state."""
        if TYPE_CHECKING:
            assert self._command_state
        LOGGER.debug("Running state value command: %s", self._command_state)
        return await async_check_output_or_log(self._command_state, self._timeout)

    async def _update_entity_state(self, now: datetime | None = None) -> None:
        """Update the state of the entity."""
        if self._process_updates is None:
            self._process_updates = asyncio.Lock()
        if self._process_updates.locked():
            LOGGER.warning(
                "Updating Command Line Cover %s took longer than the scheduled update interval %s",
                self.name,
                self._scan_interval,
            )
            return

        async with self._process_updates:
            await self._async_update()

    async def _async_update(self) -> None:
        """Update device state."""
        if self._command_state:
            payload = str(await self._async_query_state())
            if self._value_template:
                payload = self._value_template.async_render_with_possible_json_value(
                    payload, None
                )
            self._state = None
            if payload:
                self._state = int(payload)
            self._process_manual_data(payload)
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._update_entity_state(dt_util.now())

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._async_move_cover(self._command_open)
        await self._update_entity_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._async_move_cover(self._command_close)
        await self._update_entity_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._async_move_cover(self._command_stop)
        await self._update_entity_state()
