"""The Validator integration."""
from typing import Any, Dict, List, Union

import attr
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components import persistent_notification
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_BATTERY_LEVEL,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall, State, callback
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)

DOMAIN = "validator"

# pylint: disable=invalid-name
ATTRIBUTE_VALIDATE_DICT = Dict[str, Any]
# pylint: enable=invalid-name

BASE_VALIDATOR: ATTRIBUTE_VALIDATE_DICT = {
    ATTR_FRIENDLY_NAME: vol.Maybe(str),
    ATTR_SUPPORTED_FEATURES: vol.Maybe(int),
    ATTR_BATTERY_LEVEL: vol.Maybe(int),
    ATTR_ATTRIBUTION: vol.Maybe(str),
    ATTR_UNIT_OF_MEASUREMENT: vol.Maybe(str),
}


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Validator component."""

    async def do_validate(call_or_evt: Union[ServiceCall, Event]):
        await validate(
            hass,
            # During startup do not report if all entities valid
            report_if_valid=isinstance(call_or_evt, ServiceCall),
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, do_validate)
    hass.services.async_register(DOMAIN, "validate", do_validate)
    return True


async def validate(hass: HomeAssistant, *, report_if_valid=True) -> None:
    """Validate integrations."""
    report = Report()

    # Run all validate platforms
    async def _async_process_platform(hass: HomeAssistant, domain: str, platform: Any):
        """Process a platform."""

        if hasattr(platform, "async_validate_entities"):
            await platform.async_validate_entities(hass, report)

    unsub = await async_process_integration_platforms(
        hass, DOMAIN, _async_process_platform
    )
    unsub()

    title = "Validator Report"

    if len(report.entities) == 0:
        if report_if_valid:
            persistent_notification.async_create(
                hass, "No invalid entities found!", title, DOMAIN
            )
        return

    parts = [
        f"Found {len(report.entities)} invalid entit{'y' if len(report.entities) == 1 else 'ies'}."
    ]

    for entity_id, errors in report.entities.items():
        parts.append(f"\n**{entity_id}**")
        parts.extend(f"- {err}" for err in errors)

    persistent_notification.async_create(hass, "\n".join(parts), title, DOMAIN)


@attr.s
class Report:
    """Class to track warnings for entities."""

    entities: Dict[str, List[str]] = attr.ib(factory=dict, init=False)

    @callback
    def async_validate_base_attributes(self, state: State) -> None:
        """Validate the base attributes."""
        self._async_validate_dict(state.entity_id, state.attributes, BASE_VALIDATOR)

    @callback
    def async_validate_supported_features(
        self,
        state: State,
        supported_feature_validators: Dict[int, ATTRIBUTE_VALIDATE_DICT],
    ):
        """Validate supported features."""
        allowed_supported_features = 0

        for feat in supported_feature_validators:
            allowed_supported_features |= feat

        supported_features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        extra_features = abs(
            (allowed_supported_features & supported_features)
            - allowed_supported_features
        )

        if extra_features != 0:
            self.async_add_warning(
                state.entity_id, f"Unsupported feature flags found: {extra_features}"
            )

        for feat, validators in supported_feature_validators.items():
            if feat & supported_features == 0:
                continue

            self._async_validate_dict(state.entity_id, state.attributes, validators)

    @callback
    def async_add_warning(self, entity_id: str, warning: str):
        """Record a warning."""
        self.entities.setdefault(entity_id, []).append(warning)

    @callback
    def _async_validate_dict(
        self,
        entity_id: str,
        to_validate: Dict[str, Any],
        validators: ATTRIBUTE_VALIDATE_DICT,
    ) -> None:
        """Validate a dictionary."""
        for key, validator in validators.items():
            key_value = to_validate.get(key)
            try:
                validator(key_value)
            except vol.Invalid as ex:
                self.async_add_warning(
                    entity_id,
                    f"Invalid value for {key}: {humanize_error(key_value, ex)}",
                )
