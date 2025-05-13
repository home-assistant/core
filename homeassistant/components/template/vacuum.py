"""Support for Template vacuums."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

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
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_OBJECT_ID, CONF_PICTURE, DOMAIN
from .template_entity import (
    LEGACY_FIELDS as TEMPLATE_ENTITY_LEGACY_FIELDS,
    TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA,
    TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_ICON_SCHEMA,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)

_LOGGER = logging.getLogger(__name__)

CONF_VACUUMS = "vacuums"
CONF_BATTERY_LEVEL = "battery_level"
CONF_BATTERY_LEVEL_TEMPLATE = "battery_level_template"
CONF_FAN_SPEED_LIST = "fan_speeds"
CONF_FAN_SPEED = "fan_speed"
CONF_FAN_SPEED_TEMPLATE = "fan_speed_template"

ENTITY_ID_FORMAT = VACUUM_DOMAIN + ".{}"
_VALID_STATES = [
    VacuumActivity.CLEANING,
    VacuumActivity.DOCKED,
    VacuumActivity.PAUSED,
    VacuumActivity.IDLE,
    VacuumActivity.RETURNING,
    VacuumActivity.ERROR,
]

LEGACY_FIELDS = TEMPLATE_ENTITY_LEGACY_FIELDS | {
    CONF_VALUE_TEMPLATE: CONF_STATE,
    CONF_BATTERY_LEVEL_TEMPLATE: CONF_BATTERY_LEVEL,
    CONF_FAN_SPEED_TEMPLATE: CONF_FAN_SPEED,
}

VACUUM_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_BATTERY_LEVEL): cv.template,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_FAN_SPEED_LIST, default=[]): cv.ensure_list,
            vol.Optional(CONF_FAN_SPEED): cv.template,
            vol.Optional(CONF_NAME): cv.template,
            vol.Optional(CONF_PICTURE): cv.template,
            vol.Optional(CONF_STATE): cv.template,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(SERVICE_CLEAN_SPOT): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_LOCATE): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_PAUSE): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_RETURN_TO_BASE): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_SET_FAN_SPEED): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_STOP): cv.SCRIPT_SCHEMA,
            vol.Required(SERVICE_START): cv.SCRIPT_SCHEMA,
        }
    )
    .extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_ICON_SCHEMA.schema),
)

LEGACY_VACUUM_SCHEMA = vol.All(
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
    {vol.Required(CONF_VACUUMS): cv.schema_with_slug_keys(LEGACY_VACUUM_SCHEMA)}
)


def rewrite_legacy_to_modern_conf(
    hass: HomeAssistant, config: dict[str, dict]
) -> list[dict]:
    """Rewrite legacy switch configuration definitions to modern ones."""
    vacuums = []

    for object_id, entity_conf in config.items():
        entity_conf = {**entity_conf, CONF_OBJECT_ID: object_id}

        entity_conf = rewrite_common_legacy_to_modern_conf(
            hass, entity_conf, LEGACY_FIELDS
        )

        if CONF_NAME not in entity_conf:
            entity_conf[CONF_NAME] = template.Template(object_id, hass)

        vacuums.append(entity_conf)

    return vacuums


@callback
def _async_create_template_tracking_entities(
    async_add_entities: AddEntitiesCallback,
    hass: HomeAssistant,
    definitions: list[dict],
    unique_id_prefix: str | None,
) -> None:
    """Create the template switches."""
    vacuums = []

    for entity_conf in definitions:
        unique_id = entity_conf.get(CONF_UNIQUE_ID)

        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"

        vacuums.append(
            TemplateVacuum(
                hass,
                entity_conf,
                unique_id,
            )
        )

    async_add_entities(vacuums)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Template cover."""
    if discovery_info is None:
        _async_create_template_tracking_entities(
            async_add_entities,
            hass,
            rewrite_legacy_to_modern_conf(hass, config[CONF_VACUUMS]),
            None,
        )
        return

    _async_create_template_tracking_entities(
        async_add_entities,
        hass,
        discovery_info["entities"],
        discovery_info["unique_id"],
    )


class TemplateVacuum(TemplateEntity, StateVacuumEntity):
    """A template vacuum component."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id,
    ) -> None:
        """Initialize the vacuum."""
        super().__init__(hass, config=config, fallback_name=None, unique_id=unique_id)
        if (object_id := config.get(CONF_OBJECT_ID)) is not None:
            self.entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, object_id, hass=hass
            )
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        self._template = config.get(CONF_STATE)
        self._battery_level_template = config.get(CONF_BATTERY_LEVEL)
        self._fan_speed_template = config.get(CONF_FAN_SPEED)
        self._attr_supported_features = (
            VacuumEntityFeature.START | VacuumEntityFeature.STATE
        )

        for action_id, supported_feature in (
            (SERVICE_START, 0),
            (SERVICE_PAUSE, VacuumEntityFeature.PAUSE),
            (SERVICE_STOP, VacuumEntityFeature.STOP),
            (SERVICE_RETURN_TO_BASE, VacuumEntityFeature.RETURN_HOME),
            (SERVICE_CLEAN_SPOT, VacuumEntityFeature.CLEAN_SPOT),
            (SERVICE_LOCATE, VacuumEntityFeature.LOCATE),
            (SERVICE_SET_FAN_SPEED, VacuumEntityFeature.FAN_SPEED),
        ):
            # Scripts can be an empty list, therefore we need to check for None
            if (action_config := config.get(action_id)) is not None:
                self.add_script(action_id, action_config, name, DOMAIN)
                self._attr_supported_features |= supported_feature

        self._state = None
        self._battery_level = None
        self._attr_fan_speed = None

        if self._battery_level_template:
            self._attr_supported_features |= VacuumEntityFeature.BATTERY

        # List of valid fan speeds
        self._attr_fan_speed_list = config[CONF_FAN_SPEED_LIST]

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the status of the vacuum cleaner."""
        return self._state

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        await self.async_run_script(
            self._action_scripts[SERVICE_START], context=self._context
        )

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        if script := self._action_scripts.get(SERVICE_PAUSE):
            await self.async_run_script(script, context=self._context)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the cleaning task."""
        if script := self._action_scripts.get(SERVICE_STOP):
            await self.async_run_script(script, context=self._context)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        if script := self._action_scripts.get(SERVICE_RETURN_TO_BASE):
            await self.async_run_script(script, context=self._context)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        if script := self._action_scripts.get(SERVICE_CLEAN_SPOT):
            await self.async_run_script(script, context=self._context)

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        if script := self._action_scripts.get(SERVICE_LOCATE):
            await self.async_run_script(script, context=self._context)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        if fan_speed not in self._attr_fan_speed_list:
            _LOGGER.error(
                "Received invalid fan speed: %s for entity %s. Expected: %s",
                fan_speed,
                self.entity_id,
                self._attr_fan_speed_list,
            )
            return

        if script := self._action_scripts.get(SERVICE_SET_FAN_SPEED):
            await self.async_run_script(
                script, run_variables={ATTR_FAN_SPEED: fan_speed}, context=self._context
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
