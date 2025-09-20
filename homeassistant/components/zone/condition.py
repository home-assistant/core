"""Offer zone automation rules."""

from __future__ import annotations

from typing import Any, cast

import voluptuous as vol

from homeassistant.const import (
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_ZONE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ConditionErrorContainer, ConditionErrorMessage
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import move_top_level_schema_fields_to_options
from homeassistant.helpers.condition import (
    Condition,
    ConditionCheckerType,
    ConditionConfig,
    trace_condition_function,
)
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import in_zone

_OPTIONS_SCHEMA_DICT = {
    vol.Required(CONF_ENTITY_ID): cv.entity_ids,
    vol.Required("zone"): cv.entity_ids,
    # To support use_trigger_value in automation
    # Deprecated 2016/04/25
    vol.Optional("event"): vol.Any("enter", "leave"),
}
_CONDITION_SCHEMA = vol.Schema({CONF_OPTIONS: _OPTIONS_SCHEMA_DICT})


def zone(
    hass: HomeAssistant,
    zone_ent: str | State | None,
    entity: str | State | None,
) -> bool:
    """Test if zone-condition matches.

    Async friendly.
    """
    if zone_ent is None:
        raise ConditionErrorMessage("zone", "no zone specified")

    if isinstance(zone_ent, str):
        zone_ent_id = zone_ent

        if (zone_ent := hass.states.get(zone_ent)) is None:
            raise ConditionErrorMessage("zone", f"unknown zone {zone_ent_id}")

    if entity is None:
        raise ConditionErrorMessage("zone", "no entity specified")

    if isinstance(entity, str):
        entity_id = entity

        if (entity := hass.states.get(entity)) is None:
            raise ConditionErrorMessage("zone", f"unknown entity {entity_id}")
    else:
        entity_id = entity.entity_id

    if entity.state in (
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        return False

    latitude = entity.attributes.get(ATTR_LATITUDE)
    longitude = entity.attributes.get(ATTR_LONGITUDE)

    if latitude is None:
        raise ConditionErrorMessage(
            "zone", f"entity {entity_id} has no 'latitude' attribute"
        )

    if longitude is None:
        raise ConditionErrorMessage(
            "zone", f"entity {entity_id} has no 'longitude' attribute"
        )

    return in_zone(
        zone_ent, latitude, longitude, entity.attributes.get(ATTR_GPS_ACCURACY, 0)
    )


class ZoneCondition(Condition):
    """Zone condition."""

    _options: dict[str, Any]

    @classmethod
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _OPTIONS_SCHEMA_DICT
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _CONDITION_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        assert config.options is not None
        self._options = config.options

    async def async_get_checker(self) -> ConditionCheckerType:
        """Wrap action method with zone based condition."""
        entity_ids = self._options.get(CONF_ENTITY_ID, [])
        zone_entity_ids = self._options.get(CONF_ZONE, [])

        @trace_condition_function
        def if_in_zone(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
            """Test if condition."""
            errors = []

            all_ok = True
            for entity_id in entity_ids:
                entity_ok = False
                for zone_entity_id in zone_entity_ids:
                    try:
                        if zone(hass, zone_entity_id, entity_id):
                            entity_ok = True
                    except ConditionErrorMessage as ex:
                        errors.append(
                            ConditionErrorMessage(
                                "zone",
                                (
                                    f"error matching {entity_id} with {zone_entity_id}:"
                                    f" {ex.message}"
                                ),
                            )
                        )

                if not entity_ok:
                    all_ok = False

            # Raise the errors only if no definitive result was found
            if errors and not all_ok:
                raise ConditionErrorContainer("zone", errors=errors)

            return all_ok

        return if_in_zone


CONDITIONS: dict[str, type[Condition]] = {
    "_": ZoneCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the sun conditions."""
    return CONDITIONS
