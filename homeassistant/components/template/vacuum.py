"""Support for Template vacuums."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .template_entity import (
    TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)

_LOGGER = logging.getLogger(__name__)

CONF_VACUUMS = "vacuums"
CONF_BATTERY_LEVEL_TEMPLATE = "battery_level_template"
CONF_FAN_SPEED_LIST = "fan_speeds"
CONF_FAN_SPEED_TEMPLATE = "fan_speed_template"

ENTITY_ID_FORMAT = VACUUM_DOMAIN + ".{}"
_VALID_STATES = [
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_PAUSED,
    STATE_IDLE,
    STATE_RETURNING,
    STATE_ERROR,
]

VACUUM_SCHEMA = vol.All(
    cv.deprecated(CONF_ENTITY_ID),
    vol.Schema(
        {
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_BATTERY_LEVEL_TEMPLATE): cv.template,
            vol.Optional(CONF_FAN_SPEED_TEMPLATE): cv.template,
            vol.Required(SERVICE_START): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_PAUSE): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_STOP): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_RETURN_TO_BASE): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_CLEAN_SPOT): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_LOCATE): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_SET_FAN_SPEED): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_FAN_SPEED_LIST, default=[]): cv.ensure_list,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY.schema)
    .extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema),
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_VACUUMS): vol.Schema({cv.slug: VACUUM_SCHEMA})}
)


async def _async_create_entities(hass, config):
    """Create the Template Vacuums."""
    vacuums = []

    for object_id, entity_config in config[CONF_VACUUMS].items():
        entity_config = rewrite_common_legacy_to_modern_conf(hass, entity_config)
        unique_id = entity_config.get(CONF_UNIQUE_ID)

        vacuums.append(
            TemplateVacuum(
                hass,
                object_id,
                entity_config,
                unique_id,
            )
        )

    return vacuums


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template vacuums."""
    async_add_entities(await _async_create_entities(hass, config))


class TemplateVacuum(TemplateEntity, StateVacuumEntity):
    """A template vacuum component."""

    _attr_should_poll = False

    def __init__(
        self,
        hass,
        object_id,
        config,
        unique_id,
    ):
        """Initialize the vacuum."""
        super().__init__(
            hass, config=config, fallback_name=object_id, unique_id=unique_id
        )
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, object_id, hass=hass
        )
        friendly_name = self._attr_name

        self._template = config.get(CONF_VALUE_TEMPLATE)
        self._battery_level_template = config.get(CONF_BATTERY_LEVEL_TEMPLATE)
        self._fan_speed_template = config.get(CONF_FAN_SPEED_TEMPLATE)
        self._attr_supported_features = (
            VacuumEntityFeature.START | VacuumEntityFeature.STATE
        )

        self._start_script = Script(hass, config[SERVICE_START], friendly_name, DOMAIN)

        self._pause_script = None
        if pause_action := config.get(SERVICE_PAUSE):
            self._pause_script = Script(hass, pause_action, friendly_name, DOMAIN)
            self._attr_supported_features |= VacuumEntityFeature.PAUSE

        self._stop_script = None
        if stop_action := config.get(SERVICE_STOP):
            self._stop_script = Script(hass, stop_action, friendly_name, DOMAIN)
            self._attr_supported_features |= VacuumEntityFeature.STOP

        self._return_to_base_script = None
        if return_to_base_action := config.get(SERVICE_RETURN_TO_BASE):
            self._return_to_base_script = Script(
                hass, return_to_base_action, friendly_name, DOMAIN
            )
            self._attr_supported_features |= VacuumEntityFeature.RETURN_HOME

        self._clean_spot_script = None
        if clean_spot_action := config.get(SERVICE_CLEAN_SPOT):
            self._clean_spot_script = Script(
                hass, clean_spot_action, friendly_name, DOMAIN
            )
            self._attr_supported_features |= VacuumEntityFeature.CLEAN_SPOT

        self._locate_script = None
        if locate_action := config.get(SERVICE_LOCATE):
            self._locate_script = Script(hass, locate_action, friendly_name, DOMAIN)
            self._attr_supported_features |= VacuumEntityFeature.LOCATE

        self._set_fan_speed_script = None
        if set_fan_speed_action := config.get(SERVICE_SET_FAN_SPEED):
            self._set_fan_speed_script = Script(
                hass, set_fan_speed_action, friendly_name, DOMAIN
            )
            self._attr_supported_features |= VacuumEntityFeature.FAN_SPEED

        self._state = None
        self._battery_level = None
        self._attr_fan_speed = None

        if self._battery_level_template:
            self._attr_supported_features |= VacuumEntityFeature.BATTERY

        # List of valid fan speeds
        self._attr_fan_speed_list = config[CONF_FAN_SPEED_LIST]

    @property
    def state(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return self._state

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        await self.async_run_script(self._start_script, context=self._context)

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        if self._pause_script is None:
            return

        await self.async_run_script(self._pause_script, context=self._context)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the cleaning task."""
        if self._stop_script is None:
            return

        await self.async_run_script(self._stop_script, context=self._context)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        if self._return_to_base_script is None:
            return

        await self.async_run_script(self._return_to_base_script, context=self._context)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        if self._clean_spot_script is None:
            return

        await self.async_run_script(self._clean_spot_script, context=self._context)

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        if self._locate_script is None:
            return

        await self.async_run_script(self._locate_script, context=self._context)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        if self._set_fan_speed_script is None:
            return

        if fan_speed in self._attr_fan_speed_list:
            self._attr_fan_speed = fan_speed
            await self.async_run_script(
                self._set_fan_speed_script,
                run_variables={ATTR_FAN_SPEED: fan_speed},
                context=self._context,
            )
        else:
            _LOGGER.error(
                "Received invalid fan speed: %s for entity %s. Expected: %s",
                fan_speed,
                self.entity_id,
                self._attr_fan_speed_list,
            )

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if self._template is not None:
            self.add_template_attribute(
                "_state", self._template, None, self._update_state
            )
        if self._fan_speed_template is not None:
            self.add_template_attribute(
                "_fan_speed",
                self._fan_speed_template,
                None,
                self._update_fan_speed,
            )
        if self._battery_level_template is not None:
            self.add_template_attribute(
                "_battery_level",
                self._battery_level_template,
                None,
                self._update_battery_level,
                none_on_template_error=True,
            )
        super()._async_setup_templates()

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            # This is legacy behavior
            self._state = STATE_UNKNOWN
            if not self._availability_template:
                self._attr_available = True
            return

        # Validate state
        if result in _VALID_STATES:
            self._state = result
        elif result == STATE_UNKNOWN:
            self._state = None
        else:
            _LOGGER.error(
                "Received invalid vacuum state: %s for entity %s. Expected: %s",
                result,
                self.entity_id,
                ", ".join(_VALID_STATES),
            )
            self._state = None

    @callback
    def _update_battery_level(self, battery_level):
        try:
            battery_level_int = int(battery_level)
            if not 0 <= battery_level_int <= 100:
                raise ValueError  # noqa: TRY301
        except ValueError:
            _LOGGER.error(
                "Received invalid battery level: %s for entity %s. Expected: 0-100",
                battery_level,
                self.entity_id,
            )
            self._attr_battery_level = None
            return

        self._attr_battery_level = battery_level_int

    @callback
    def _update_fan_speed(self, fan_speed):
        if isinstance(fan_speed, TemplateError):
            # This is legacy behavior
            self._attr_fan_speed = None
            self._state = None
            return

        if fan_speed in self._attr_fan_speed_list:
            self._attr_fan_speed = fan_speed
        elif fan_speed == STATE_UNKNOWN:
            self._attr_fan_speed = None
        else:
            _LOGGER.error(
                "Received invalid fan speed: %s for entity %s. Expected: %s",
                fan_speed,
                self.entity_id,
                self._attr_fan_speed_list,
            )
            self._attr_fan_speed = None
