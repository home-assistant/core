"""Offer zone automation rules."""

from typing import Any, Unpack, cast, override

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    DeviceTrackerEntityStateAttribute,
)
from homeassistant.components.person import (
    DOMAIN as PERSON_DOMAIN,
    PersonEntityStateAttribute,
)
from homeassistant.const import (
    ATTR_GPS_ACCURACY,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_OPTIONS,
    CONF_TARGET,
    CONF_ZONE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityStateAttribute,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ConditionErrorContainer, ConditionErrorMessage
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import (
    DomainSpec,
    move_top_level_schema_fields_to_options,
)
from homeassistant.helpers.condition import (
    ATTR_BEHAVIOR,
    BEHAVIOR_ANY,
    ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL,
    Condition,
    ConditionCheckParams,
    ConditionConfig,
    EntityConditionBase,
)
from homeassistant.helpers.typing import ConfigType

from . import in_zone
from .const import DOMAIN
from .helpers import get_in_zones_attribute

_OPTIONS_SCHEMA_DICT: dict[vol.Marker, Any] = {
    vol.Required(CONF_ENTITY_ID): cv.entity_ids,
    vol.Required("zone"): cv.entity_ids,
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

    # Prefer the in_zones attribute reported by the entity (e.g. person,
    # device_tracker) over recomputing membership from coordinates.
    if (in_zones_attr := get_in_zones_attribute(entity)) is not None and (
        in_zones := entity.attributes.get(in_zones_attr)
    ) is not None:
        return zone_ent.entity_id in in_zones

    latitude = entity.attributes.get(EntityStateAttribute.LATITUDE)
    longitude = entity.attributes.get(EntityStateAttribute.LONGITUDE)

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
    @override
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _OPTIONS_SCHEMA_DICT
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _CONDITION_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        assert config.options is not None
        self._options = config.options
        self._entity_ids = self._options.get(CONF_ENTITY_ID, [])
        self._zone_entity_ids = self._options.get(CONF_ZONE, [])

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Test if condition."""
        errors = []

        all_ok = True
        for entity_id in self._entity_ids:
            entity_ok = False
            for zone_entity_id in self._zone_entity_ids:
                try:
                    if zone(self._hass, zone_entity_id, entity_id):
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


_DOMAIN_SPECS: dict[str, DomainSpec] = {
    PERSON_DOMAIN: DomainSpec(value_source=PersonEntityStateAttribute.IN_ZONES),
    DEVICE_TRACKER_DOMAIN: DomainSpec(
        value_source=DeviceTrackerEntityStateAttribute.IN_ZONES
    ),
}

_ZONE_CONDITION_SCHEMA = ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_ZONE): cv.entity_domain(DOMAIN),
        },
    }
)


class _ZoneTargetConditionBase(EntityConditionBase):
    """Base for zone-target conditions on person and device_tracker entities."""

    _domain_specs = _DOMAIN_SPECS
    _schema = _ZONE_CONDITION_SCHEMA

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize the condition."""
        super().__init__(hass, config)
        assert config.options is not None
        self._zone: str = config.options[CONF_ZONE]

    def _in_target_zone(self, entity_state: State) -> bool:
        """Check if the entity is currently in the selected zone."""
        if (in_zones_attr := get_in_zones_attribute(entity_state)) and (
            in_zones := entity_state.attributes.get(in_zones_attr)
        ):
            return self._zone in in_zones
        return False


class InZoneCondition(_ZoneTargetConditionBase):
    """Condition: targeted entity is in the selected zone."""

    @override
    def is_valid_state(self, entity_state: State) -> bool:
        """Check that the entity is in the selected zone."""
        return self._in_target_zone(entity_state)


class NotInZoneCondition(_ZoneTargetConditionBase):
    """Condition: targeted entity is not in the selected zone."""

    @override
    def is_valid_state(self, entity_state: State) -> bool:
        """Check that the entity is not in the selected zone."""
        return not self._in_target_zone(entity_state)


_OCCUPANCY_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default={}): {
            vol.Required(CONF_ZONE): cv.entity_domain(DOMAIN),
            vol.Optional(CONF_FOR): cv.positive_time_period,
        },
    }
)


class _ZoneOccupancyConditionBase(EntityConditionBase):
    """Base for zone occupancy conditions (single zone, no behavior)."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _schema = _OCCUPANCY_CONDITION_SCHEMA

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config and synthesize a target from the zone option.

        We synthesize a target because we allow users to pick a single zone
        to monitor, not a target.
        """
        config = cast(ConfigType, cls._schema(config))
        zone_entity_id: str = config[CONF_OPTIONS][CONF_ZONE]
        config[CONF_TARGET] = {CONF_ENTITY_ID: [zone_entity_id]}
        # `behavior` is needed by `EntityConditionBase.__init__`
        config[CONF_OPTIONS][ATTR_BEHAVIOR] = BEHAVIOR_ANY
        return config

    @staticmethod
    def _occupancy_count(entity_state: State) -> int | None:
        """Return the zone's persons-in-zone count; None if unparsable."""
        try:
            return int(entity_state.state)
        except TypeError, ValueError:
            return None

    @classmethod
    def _is_occupied(cls, entity_state: State) -> bool:
        """Return True if the zone has at least one occupant."""
        count = cls._occupancy_count(entity_state)
        return count is not None and count >= 1


class OccupancyIsDetectedCondition(_ZoneOccupancyConditionBase):
    """Condition: the selected zone is occupied."""

    @override
    def is_valid_state(self, entity_state: State) -> bool:
        """Check that the zone is occupied."""
        return self._is_occupied(entity_state)


class OccupancyIsNotDetectedCondition(_ZoneOccupancyConditionBase):
    """Condition: the selected zone is empty."""

    @override
    def is_valid_state(self, entity_state: State) -> bool:
        """Check that the zone is empty (count == 0)."""
        return self._occupancy_count(entity_state) == 0


CONDITIONS: dict[str, type[Condition]] = {
    "_": ZoneCondition,
    "in_zone": InZoneCondition,
    "not_in_zone": NotInZoneCondition,
    "occupancy_is_detected": OccupancyIsDetectedCondition,
    "occupancy_is_not_detected": OccupancyIsNotDetectedCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the zone conditions."""
    return CONDITIONS
