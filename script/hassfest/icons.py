"""Validate integration icon translation files."""

from typing import Any

import orjson
import probatio
from probatio.humanize import humanize_error

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.icon import convert_shorthand_service_icon

from .model import Config, Integration, IntegrationType
from .translations import translation_key_validator


def icon_value_validator(value: Any) -> str:
    """Validate that the icon is a valid icon."""
    value = cv.string_with_no_html(value)
    if not value.startswith("mdi:"):
        raise probatio.Invalid(
            "The icon needs to be a valid icon from Material"
            " Design Icons and start with `mdi:`"
        )
    return str(value)


def range_key_validator(value: str) -> str:
    """Validate that range key value is numeric."""
    try:
        float(value)
    except (TypeError, ValueError) as err:
        raise probatio.Invalid(
            f"Invalid range key '{value}', needs to be numeric."
        ) from err

    return value


def require_default_icon_validator(value: dict) -> dict:
    """Validate that a default icon is set."""
    if "_" not in value:
        raise probatio.Invalid(
            "An entity component needs to have a default icon defined with `_`"
        )
    return value


def ensure_not_same_as_default(value: dict) -> dict:
    """Validate an icon isn't the same as its default icon."""
    for translation_key, section in value.items():
        if (default := section.get("default")) and (states := section.get("state")):
            for state, icon in states.items():
                if icon == default:
                    raise probatio.Invalid(
                        f"The icon for state `{translation_key}.{state}` is the"
                        " same as the default icon and thus can be removed"
                    )

    return value


def ensure_range_is_sorted(value: dict) -> dict:
    """Validate that range values are sorted in ascending order."""
    for section_key, section in value.items():
        # Only validate range if one exists and this is an icon definition
        if ranges := section.get("range"):
            try:
                range_values = [float(key) for key in ranges]
            except ValueError as err:
                raise probatio.Invalid(
                    f"Range values for `{section_key}` must be numeric"
                ) from err

            if range_values != sorted(range_values):
                raise probatio.Invalid(
                    f"Range values for `{section_key}` must be in ascending order"
                )

    return value


DATA_ENTRY_ICONS_SCHEMA = probatio.Schema(
    {
        "step": {
            str: {
                "sections": {
                    str: icon_value_validator,
                }
            }
        }
    }
)


CORE_SERVICE_ICONS_SCHEMA = cv.schema_with_slug_keys(
    probatio.Schema(
        {
            probatio.Optional("service"): icon_value_validator,
            probatio.Optional("sections"): cv.schema_with_slug_keys(
                icon_value_validator, slug_validator=translation_key_validator
            ),
        }
    ),
    slug_validator=translation_key_validator,
)


CUSTOM_INTEGRATION_SERVICE_ICONS_SCHEMA = cv.schema_with_slug_keys(
    probatio.All(
        convert_shorthand_service_icon,
        probatio.Schema(
            {
                probatio.Optional("service"): icon_value_validator,
                probatio.Optional("sections"): cv.schema_with_slug_keys(
                    icon_value_validator, slug_validator=translation_key_validator
                ),
            }
        ),
    ),
    slug_validator=translation_key_validator,
)


CONDITION_ICONS_SCHEMA = cv.schema_with_slug_keys(
    probatio.Schema(
        {
            probatio.Optional("condition"): icon_value_validator,
        }
    ),
    slug_validator=cv.underscore_slug,
)


TRIGGER_ICONS_SCHEMA = cv.schema_with_slug_keys(
    probatio.Schema(
        {
            probatio.Optional("trigger"): icon_value_validator,
        }
    ),
    slug_validator=cv.underscore_slug,
)


INTEGRATION_CATEGORY_ICONS_SCHEMA = cv.schema_with_slug_keys(
    {
        probatio.Required("default"): icon_value_validator,
        probatio.Optional("subcategory"): cv.schema_with_slug_keys(
            {probatio.Required("default"): icon_value_validator},
            slug_validator=translation_key_validator,
        ),
    },
    slug_validator=translation_key_validator,
)


INTEGRATION_CONNECTIVITY_ICONS_SCHEMA = cv.schema_with_slug_keys(
    {probatio.Required("default"): icon_value_validator},
    slug_validator=translation_key_validator,
)


def icon_schema(
    core_integration: bool, integration_type: IntegrationType, no_entity_platform: bool
) -> probatio.Schema:
    """Create an icon schema."""

    state_validator = cv.schema_with_slug_keys(
        icon_value_validator,
        slug_validator=translation_key_validator,
    )

    range_validator = cv.schema_with_slug_keys(
        icon_value_validator,
        slug_validator=range_key_validator,
    )

    def icon_schema_slug(marker: type[probatio.Marker]) -> dict[probatio.Marker, Any]:
        return {
            marker("default"): icon_value_validator,
            probatio.Optional("state"): state_validator,
            probatio.Optional("range"): range_validator,
            probatio.Optional("state_attributes"): probatio.All(
                cv.schema_with_slug_keys(
                    {
                        marker("default"): icon_value_validator,
                        probatio.Optional("state"): state_validator,
                        probatio.Optional("range"): range_validator,
                    },
                    slug_validator=translation_key_validator,
                ),
                ensure_not_same_as_default,
                ensure_range_is_sorted,
            ),
        }

    schema = probatio.Schema(
        {
            probatio.Optional("conditions"): CONDITION_ICONS_SCHEMA,
            probatio.Optional("config"): DATA_ENTRY_ICONS_SCHEMA,
            probatio.Optional("issues"): probatio.Schema(
                {str: {"fix_flow": DATA_ENTRY_ICONS_SCHEMA}}
            ),
            probatio.Optional("options"): DATA_ENTRY_ICONS_SCHEMA,
            probatio.Optional("services"): CORE_SERVICE_ICONS_SCHEMA
            if core_integration
            else CUSTOM_INTEGRATION_SERVICE_ICONS_SCHEMA,
            probatio.Optional("triggers"): TRIGGER_ICONS_SCHEMA,
        }
    )

    if integration_type in (
        IntegrationType.ENTITY,
        IntegrationType.HELPER,
        IntegrationType.SYSTEM,
    ):
        if integration_type != IntegrationType.ENTITY or no_entity_platform:
            field = probatio.Optional("entity_component")
        else:
            field = probatio.Required("entity_component")
        schema = schema.extend(
            {
                field: probatio.All(
                    cv.schema_with_slug_keys(
                        icon_schema_slug(probatio.Required),
                        slug_validator=probatio.Any("_", cv.slug),
                    ),
                    require_default_icon_validator,
                    ensure_not_same_as_default,
                    ensure_range_is_sorted,
                )
            }
        )
    if integration_type != IntegrationType.ENTITY:
        schema = schema.extend(
            {
                probatio.Optional("entity"): probatio.All(
                    cv.schema_with_slug_keys(
                        cv.schema_with_slug_keys(
                            icon_schema_slug(probatio.Optional),
                            slug_validator=translation_key_validator,
                        ),
                        slug_validator=cv.slug,
                    ),
                    ensure_not_same_as_default,
                )
            }
        )
    return schema


def integration_category_keys(categories: dict[str, Any]) -> set[str]:
    """Return the category and subcategory keys, like `energy.meters_monitoring`."""
    keys = set()
    for category, details in categories.items():
        keys.add(category)
        keys.update(
            f"{category}.{subcategory}"
            for subcategory in details.get("subcategory", {})
        )

    return keys


def validate_integration_category_icons(
    integration: Integration, icons: dict[str, Any]
) -> None:
    """Validate every integration category has an icon, and every icon a category."""
    # Invalid strings are reported by the json and translations plugins.
    try:
        strings = orjson.loads((integration.path / "strings.json").read_text())
        categories = integration_category_keys(strings.get("integration_category", {}))
    except ValueError, AttributeError, TypeError:
        return

    category_icons = integration_category_keys(icons.get("integration_category", {}))

    for key in sorted(categories - category_icons):
        integration.add_error("icons", f"Integration category `{key}` has no icon")

    for key in sorted(category_icons - categories):
        integration.add_error("icons", f"Icon for unknown integration category `{key}`")


def validate_integration_connectivity_icons(
    integration: Integration, icons: dict[str, Any]
) -> None:
    """Validate every connectivity value has an icon, and every icon a value."""
    # Invalid strings are reported by the json and translations plugins.
    try:
        strings = orjson.loads((integration.path / "strings.json").read_text())
        values = set(strings.get("integration_connectivity", {}))
    except ValueError, AttributeError, TypeError:
        return

    value_icons = set(icons.get("integration_connectivity", {}))

    for key in sorted(values - value_icons):
        integration.add_error("icons", f"Connectivity `{key}` has no icon")

    for key in sorted(value_icons - values):
        integration.add_error("icons", f"Icon for unknown connectivity `{key}`")


def validate_icon_file(config: Config, integration: Integration) -> None:
    """Validate icon file for integration."""
    icons_file = integration.path / "icons.json"
    if not icons_file.is_file():
        return

    name = str(icons_file.relative_to(integration.path))

    try:
        icons = orjson.loads(icons_file.read_text())
    except ValueError as err:
        integration.add_error("icons", f"Invalid JSON in {name}: {err}")
        return

    no_entity_platform = integration.domain in ("notify", "image_processing")

    schema = icon_schema(
        integration.core, integration.integration_type, no_entity_platform
    )
    if integration.domain == "homeassistant":
        schema = schema.extend(
            {
                probatio.Optional(
                    "integration_category"
                ): INTEGRATION_CATEGORY_ICONS_SCHEMA,
                probatio.Optional(
                    "integration_connectivity"
                ): INTEGRATION_CONNECTIVITY_ICONS_SCHEMA,
            }
        )

    try:
        schema(icons)
    except probatio.Invalid as err:
        integration.add_error("icons", f"Invalid {name}: {humanize_error(icons, err)}")
        return

    if integration.domain == "homeassistant":
        validate_integration_category_icons(integration, icons)
        validate_integration_connectivity_icons(integration, icons)


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle JSON files inside integrations."""
    for integration in integrations.values():
        validate_icon_file(config, integration)
