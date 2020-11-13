"""Selectors for Home Assistant."""
from typing import Any, Callable, Dict, cast

import voluptuous as vol

from homeassistant.util import decorator

SELECTORS = decorator.Registry()


def validate_selector(config: Any) -> Dict:
    """Validate a selector."""
    if not isinstance(config, dict):
        raise vol.Invalid("Expected a dictionary")

    if len(config) != 1:
        raise vol.Invalid(f"Only one type can be specified. Found {', '.join(config)}")

    selector_type = list(config)[0]

    seslector_class = SELECTORS.get(selector_type)

    if seslector_class is None:
        raise vol.Invalid(f"Unknown selector type {selector_type} found")

    return cast(Dict, seslector_class.CONFIG_SCHEMA(config[selector_type]))


class Selector:
    """Base class for selectors."""

    CONFIG_SCHEMA: Callable


@SELECTORS.register("entity")
class EntitySelector(Selector):
    """Selector of a single entity."""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("integration"): str,
            vol.Optional("domain"): str,
        }
    )


@SELECTORS.register("device")
class DeviceSelector(Selector):
    """Selector of a single device."""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("integration"): str,
            vol.Optional("manufacturer"): str,
            vol.Optional("model"): str,
        }
    )
