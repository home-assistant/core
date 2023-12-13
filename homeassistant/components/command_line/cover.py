"""Support for command line covers."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.cover import CoverDeviceClass, CoverEntity
from homeassistant.const import (
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STATE,
    CONF_COMMAND_STOP,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
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

SCAN_INTERVAL = timedelta(seconds=15)

_VALID_STATES = [
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up cover controlled by shell commands."""

    covers = []
    discovery_info = cast(DiscoveryInfoType, discovery_info)
    entities: dict[str, Any] = {slugify(discovery_info[CONF_NAME]): discovery_info}

    for device_name, device_config in entities.items():
        device_class: CoverDeviceClass | None = device_config.get(CONF_DEVICE_CLASS)
        value_template: Template | None = device_config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = hass
        trigger_entity_config = {
            CONF_UNIQUE_ID: device_config.get(CONF_UNIQUE_ID),
            CONF_NAME: Template(device_config.get(CONF_NAME, device_name), hass),
            CONF_DEVICE_CLASS: device_class,
        }

        covers.append(
            CommandCover(
                trigger_entity_config,
                device_config[CONF_COMMAND_OPEN],
                device_config[CONF_COMMAND_CLOSE],
                device_config[CONF_COMMAND_STOP],
                device_config.get(CONF_COMMAND_STATE),
                value_template,
                device_config[CONF_COMMAND_TIMEOUT],
                device_config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL),
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
        self._openclose = False
        self._command_open = command_open
        self._command_close = command_close
        self._command_stop = command_stop
        self._command_state = command_state
        self._value_template = value_template
        self._is_opening = False
        self._is_closing = False
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

    def _move_cover(self, command: str) -> bool:
        """Execute the actual commands."""
        LOGGER.info("Running command: %s", command)

        returncode = call_shell_with_timeout(command, self._timeout)
        success = returncode == 0

        if not success:
            LOGGER.error(
                "Command failed (with return code %s): %s", returncode, command
            )

        return success

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._state is not None:
            return self._state == 0
        return None

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is currently opening."""
        return self._is_opening

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is currently closing."""
        return self._is_closing

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        This is skipped if the state is provided in open/ close format.
        None is unknown, 0 is closed, 100 is fully open.
        """
        if self._openclose is False:
            return self._state
        return None

    def _query_state(self) -> str | None:
        """Query for the state."""
        if self._command_state:
            LOGGER.info("Running state value command: %s", self._command_state)
            return check_output_or_log(self._command_state, self._timeout)
        if TYPE_CHECKING:
            return None

    async def _update_entity_state(self, now) -> None:
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
            payload = str(await self.hass.async_add_executor_job(self._query_state))
            if self._value_template:
                payload = self._value_template.async_render_with_possible_json_value(
                    payload, None
                )
            self._state = None
            if payload:
                LOGGER.info(
                    "Received payload: %s from %s",
                    payload,
                    self.entity_id,
                )
                if payload in _VALID_STATES:
                    self._openclose = True
                    if payload in STATE_OPEN:
                        self._state = 100
                    else:
                        self._state = 0
                    self._is_opening = payload == STATE_OPENING
                    self._is_closing = payload == STATE_CLOSING
                else:
                    try:
                        float(payload)
                    except ValueError:
                        LOGGER.error(
                            "The state of %s must be one of [%s, %s, %s, %s] or a number between 0 and 100. The received state was: %s",
                            self.entity_id,
                            STATE_CLOSED,
                            STATE_CLOSING,
                            STATE_OPEN,
                            STATE_OPENING,
                            payload,
                        )
                        return
                    if int(payload) < 0 or int(payload) > 100:
                        LOGGER.error(
                            "The state of %s must be one of [%s, %s, %s, %s] or a number between 0 and 100. The received state was: %s",
                            self.entity_id,
                            STATE_CLOSED,
                            STATE_CLOSING,
                            STATE_OPEN,
                            STATE_OPENING,
                            payload,
                        )
                    else:
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
        await self.hass.async_add_executor_job(self._move_cover, self._command_open)
        await self._update_entity_state(None)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.hass.async_add_executor_job(self._move_cover, self._command_close)
        await self._update_entity_state(None)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.hass.async_add_executor_job(self._move_cover, self._command_stop)
        await self._update_entity_state(None)
