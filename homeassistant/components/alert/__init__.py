"""Support for repeating alerts when conditions are met.

DEVELOPMENT OF THE ALERT INTEGRATION IS FROZEN.
"""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_REPEAT,
    CONF_STATE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ALERT_MESSAGE,
    CONF_CAN_ACK,
    CONF_DATA,
    CONF_DONE_MESSAGE,
    CONF_NOTIFIERS,
    CONF_SKIP_FIRST,
    CONF_TITLE,
    DEFAULT_CAN_ACK,
    DEFAULT_SKIP_FIRST,
    DOMAIN,
    LOGGER,
)
from .entity import AlertEntity

type AlertConfigEntry = ConfigEntry[str]

ALERT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_STATE, default=STATE_ON): cv.string,
        vol.Required(CONF_REPEAT): vol.All(
            cv.ensure_list,
            [vol.Coerce(float)],
            # Minimum delay is 1 second = 0.016 minutes
            [vol.Range(min=0.016)],
        ),
        vol.Optional(CONF_CAN_ACK, default=DEFAULT_CAN_ACK): cv.boolean,
        vol.Optional(CONF_SKIP_FIRST, default=DEFAULT_SKIP_FIRST): cv.boolean,
        vol.Optional(CONF_ALERT_MESSAGE): cv.template,
        vol.Optional(CONF_DONE_MESSAGE): cv.template,
        vol.Optional(CONF_TITLE): cv.template,
        vol.Optional(CONF_DATA): dict,
        vol.Optional(CONF_NOTIFIERS, default=list): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(ALERT_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


def _alert_from_yaml(
    hass: HomeAssistant, object_id: str, cfg: dict[str, Any] | None
) -> AlertEntity:
    """Build an AlertEntity from a YAML alert configuration."""
    if not cfg:
        cfg = {}

    return AlertEntity(
        hass,
        object_id,
        cfg[CONF_NAME],
        cfg[CONF_ENTITY_ID],
        cfg[CONF_STATE],
        cfg[CONF_REPEAT],
        cfg[CONF_SKIP_FIRST],
        cfg.get(CONF_ALERT_MESSAGE),
        cfg.get(CONF_DONE_MESSAGE),
        cfg[CONF_NOTIFIERS],
        cfg[CONF_CAN_ACK],
        cfg.get(CONF_TITLE),
        cfg.get(CONF_DATA),
    )


def _template_from_string(hass: HomeAssistant, value: str | None) -> Template | None:
    """Wrap an optional string in a Template attached to hass."""
    if value is None:
        return None
    return Template(value, hass)


def _alert_from_entry(hass: HomeAssistant, entry: AlertConfigEntry) -> AlertEntity:
    """Build an AlertEntity from a config entry."""
    options = entry.options
    return AlertEntity(
        hass,
        None,
        entry.title,
        options[CONF_ENTITY_ID],
        options.get(CONF_STATE, STATE_ON),
        [float(value) for value in options[CONF_REPEAT]],
        options.get(CONF_SKIP_FIRST, DEFAULT_SKIP_FIRST),
        _template_from_string(hass, options.get(CONF_ALERT_MESSAGE)),
        _template_from_string(hass, options.get(CONF_DONE_MESSAGE)),
        list(options.get(CONF_NOTIFIERS, [])),
        options.get(CONF_CAN_ACK, DEFAULT_CAN_ACK),
        _template_from_string(hass, options.get(CONF_TITLE)),
        options.get(CONF_DATA),
        unique_id=entry.entry_id,
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Alert component.

    DEVELOPMENT OF THE ALERT INTEGRATION IS FROZEN.
    """
    component = hass.data[DOMAIN] = EntityComponent[AlertEntity](LOGGER, DOMAIN, hass)

    component.async_register_entity_service(SERVICE_TURN_OFF, None, "async_turn_off")
    component.async_register_entity_service(SERVICE_TURN_ON, None, "async_turn_on")
    component.async_register_entity_service(SERVICE_TOGGLE, None, "async_toggle")

    yaml_entities = [
        _alert_from_yaml(hass, object_id, cfg)
        for object_id, cfg in config.get(DOMAIN, {}).items()
    ]
    if yaml_entities:
        await component.async_add_entities(yaml_entities)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: AlertConfigEntry) -> bool:
    """Set up an alert from a config entry."""
    component: EntityComponent[AlertEntity] = hass.data[DOMAIN]
    alert = _alert_from_entry(hass, entry)
    await component.async_add_entities([alert])
    entry.runtime_data = alert.entity_id
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AlertConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[AlertEntity] = hass.data[DOMAIN]
    await component.async_remove_entity(entry.runtime_data)
    return True
