"""Provides conditions for covers."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.condition import Condition, EntityConditionBase

from .const import ATTR_IS_CLOSED, DOMAIN, CoverDeviceClass
from .models import CoverDomainSpec


class CoverConditionBase(EntityConditionBase[CoverDomainSpec]):
    """Base condition for cover state checks."""

    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the state matches the expected cover state."""
        domain_spec = self._domain_specs[entity_state.domain]
        if domain_spec.value_source is not None:
            return (
                entity_state.attributes.get(domain_spec.value_source)
                == domain_spec.target_value
            )
        return entity_state.state == domain_spec.target_value


def make_cover_is_open_condition(
    *, device_classes: dict[str, str]
) -> type[CoverConditionBase]:
    """Create a condition for cover is open."""

    class CoverIsOpenCondition(CoverConditionBase):
        """Condition for cover is open."""

        _domain_specs = {
            domain: CoverDomainSpec(
                device_class=dc,
                value_source=ATTR_IS_CLOSED if domain == DOMAIN else None,
                target_value=False if domain == DOMAIN else STATE_ON,
            )
            for domain, dc in device_classes.items()
        }

    return CoverIsOpenCondition


def make_cover_is_closed_condition(
    *, device_classes: dict[str, str]
) -> type[CoverConditionBase]:
    """Create a condition for cover is closed."""

    class CoverIsClosedCondition(CoverConditionBase):
        """Condition for cover is closed."""

        _domain_specs = {
            domain: CoverDomainSpec(
                device_class=dc,
                value_source=ATTR_IS_CLOSED if domain == DOMAIN else None,
                target_value=True if domain == DOMAIN else STATE_OFF,
            )
            for domain, dc in device_classes.items()
        }

    return CoverIsClosedCondition


DEVICE_CLASSES_AWNING: dict[str, str] = {DOMAIN: CoverDeviceClass.AWNING}
DEVICE_CLASSES_BLIND: dict[str, str] = {DOMAIN: CoverDeviceClass.BLIND}
DEVICE_CLASSES_CURTAIN: dict[str, str] = {DOMAIN: CoverDeviceClass.CURTAIN}
DEVICE_CLASSES_SHADE: dict[str, str] = {DOMAIN: CoverDeviceClass.SHADE}
DEVICE_CLASSES_SHUTTER: dict[str, str] = {DOMAIN: CoverDeviceClass.SHUTTER}

CONDITIONS: dict[str, type[Condition]] = {
    "awning_is_closed": make_cover_is_closed_condition(
        device_classes=DEVICE_CLASSES_AWNING
    ),
    "awning_is_open": make_cover_is_open_condition(
        device_classes=DEVICE_CLASSES_AWNING
    ),
    "blind_is_closed": make_cover_is_closed_condition(
        device_classes=DEVICE_CLASSES_BLIND
    ),
    "blind_is_open": make_cover_is_open_condition(device_classes=DEVICE_CLASSES_BLIND),
    "curtain_is_closed": make_cover_is_closed_condition(
        device_classes=DEVICE_CLASSES_CURTAIN
    ),
    "curtain_is_open": make_cover_is_open_condition(
        device_classes=DEVICE_CLASSES_CURTAIN
    ),
    "shade_is_closed": make_cover_is_closed_condition(
        device_classes=DEVICE_CLASSES_SHADE
    ),
    "shade_is_open": make_cover_is_open_condition(device_classes=DEVICE_CLASSES_SHADE),
    "shutter_is_closed": make_cover_is_closed_condition(
        device_classes=DEVICE_CLASSES_SHUTTER
    ),
    "shutter_is_open": make_cover_is_open_condition(
        device_classes=DEVICE_CLASSES_SHUTTER
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for covers."""
    return CONDITIONS
