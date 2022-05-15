"""Support for command line covers."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.cover import PLATFORM_SCHEMA, CoverEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STATE,
    CONF_COMMAND_STOP,
    CONF_COVERS,
    CONF_FRIENDLY_NAME,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN
from .util import call_shell_with_timeout, check_output_or_log

_LOGGER = logging.getLogger(__name__)

COVER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COMMAND_CLOSE, default="true"): cv.string,
        vol.Optional(CONF_COMMAND_OPEN, default="true"): cv.string,
        vol.Optional(CONF_COMMAND_STATE): cv.string,
        vol.Optional(CONF_COMMAND_STOP, default="true"): cv.string,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_COVERS): cv.schema_with_slug_keys(COVER_SCHEMA)}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up cover controlled by shell commands."""

    _LOGGER.warning(
        # Command Line config flow added in 2022.6 and should be removed in 2022.8
        "Configuration of the Command Line Cover platform in YAML is deprecated and "
        "will be removed in Home Assistant 2022.8; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )

    devices: dict[str, Any] = config.get(CONF_COVERS, {})

    if devices == {}:
        _LOGGER.error("No covers to import")
        return

    for device_name, device_config in devices.items():
        value_template: Template | None = device_config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            template_value: str = value_template.template
        new_config = {
            CONF_NAME: device_config.get(CONF_FRIENDLY_NAME, device_name),
            CONF_COMMAND_OPEN: device_config[CONF_COMMAND_OPEN],
            CONF_COMMAND_CLOSE: device_config[CONF_COMMAND_CLOSE],
            CONF_COMMAND_STOP: device_config[CONF_COMMAND_STOP],
            CONF_COMMAND_STATE: device_config.get(CONF_COMMAND_STATE),
            CONF_VALUE_TEMPLATE: template_value if value_template else None,
            CONF_COMMAND_TIMEOUT: device_config[CONF_COMMAND_TIMEOUT],
            CONF_UNIQUE_ID: device_config.get(CONF_UNIQUE_ID),
            CONF_PLATFORM: Platform.COVER,
        }
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=new_config,
            )
        )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Command Line Cover entry."""

    command_open = entry.options[CONF_COMMAND_OPEN]
    command_close = entry.options[CONF_COMMAND_CLOSE]
    command_stop = entry.options[CONF_COMMAND_STOP]
    command_state = entry.options.get(CONF_COMMAND_STATE)
    value_template = entry.options.get(CONF_VALUE_TEMPLATE)
    name = entry.options[CONF_NAME]
    command_timeout = entry.options[CONF_COMMAND_TIMEOUT]
    unique_id = entry.options.get(CONF_UNIQUE_ID)
    if value_template is not None:
        template_value = Template(value_template)
        template_value.hass = hass

    async_add_entities(
        [
            CommandCover(
                name,
                command_open,
                command_close,
                command_stop,
                command_state,
                template_value if value_template else None,
                command_timeout,
                unique_id,
                entry.entry_id,
            )
        ]
    )


class CommandCover(CoverEntity):
    """Representation a command line cover."""

    def __init__(
        self,
        name: str,
        command_open: str,
        command_close: str,
        command_stop: str,
        command_state: str | None,
        value_template: Template | None,
        timeout: int,
        unique_id: str | None,
        entry_id: str,
    ) -> None:
        """Initialize the cover."""
        self._attr_name = name
        self._state: int | None = None
        self._command_open = command_open
        self._command_close = command_close
        self._command_stop = command_stop
        self._command_state = command_state
        self._value_template = value_template
        self._timeout = timeout
        self._attr_unique_id = unique_id if unique_id else entry_id
        self._attr_should_poll = bool(command_state)

    def _move_cover(self, command: str) -> bool:
        """Execute the actual commands."""
        _LOGGER.info("Running command: %s", command)

        returncode = call_shell_with_timeout(command, self._timeout)
        success = returncode == 0

        if not success:
            _LOGGER.error(
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

    def _query_state(self) -> str | None:
        """Query for the state."""
        if self._command_state:
            _LOGGER.info("Running state value command: %s", self._command_state)
            return check_output_or_log(self._command_state, self._timeout)
        if TYPE_CHECKING:
            return None

    def update(self) -> None:
        """Update device state."""
        if self._command_state:
            payload = str(self._query_state())
            if self._value_template:
                payload = self._value_template.render_with_possible_json_value(payload)
            self._state = int(payload)

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._move_cover(self._command_open)

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._move_cover(self._command_close)

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._move_cover(self._command_stop)
