"""Repairs platform for the template integration."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import os

import probatio

from homeassistant.components.blueprint import CONF_USE_BLUEPRINT
from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_PATH, CONF_UNIQUE_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.selector import DeviceSelector

from . import validators as tcv
from .const import (
    CONF_ATTRIBUTES,
    DEPRECATED_ATTRIBUTES,
    DOMAIN,
    WEATHER_DEPRECATED_TEMPLATE_OPTIONS,
    TemplateConfig,
    TemplateConfigSections,
)

DEPRECATED_TEMPLATE_OPTIONS_ISSUE_ID = "deprecated_weather_template_options"
DEPRECATED_TEMPLATE_OPTIONS_BLUEPRINT_TRANSLATION_KEY = (
    "deprecated_weather_template_options_blueprint"
)
DEPRECATED_TEMPLATE_OPTIONS_BREAKS_IN = "2027.6.0"
DEPRECATED_ATTRIBUTES_ISSUE_ID = "deprecated_attributes"
DEPRECATED_ATTRIBUTES_BLUEPRINT_TRANSLATION_KEY = "deprecated_attributes_blueprint"
DEPRECATED_ATTRIBUTES_BREAKS_IN = "2027.6.0"

type OptionLocations = dict[str, list[dict[str, tuple[str, int]]]]


@dataclass(frozen=True, kw_only=True)
class DeprecatedOptions:
    """Entity options deprecated in favor of a replacement option."""

    issue_id: str
    blueprint_translation_key: str
    breaks_in_ha_version: str
    # Platform to deprecated option to its replacement
    replacements: Mapping[Platform, Mapping[str, str]]
    locations: Callable[[TemplateConfig], OptionLocations | None]
    # The entity option holding the deprecated options, the entity config when None
    parent_option: str | None = None
    # The platform is part of the issue when the deprecation spans platforms
    per_platform: bool = False


WEATHER_DEPRECATED_TEMPLATE_OPTIONS_ISSUES = DeprecatedOptions(
    issue_id=DEPRECATED_TEMPLATE_OPTIONS_ISSUE_ID,
    blueprint_translation_key=DEPRECATED_TEMPLATE_OPTIONS_BLUEPRINT_TRANSLATION_KEY,
    breaks_in_ha_version=DEPRECATED_TEMPLATE_OPTIONS_BREAKS_IN,
    replacements={Platform.WEATHER: WEATHER_DEPRECATED_TEMPLATE_OPTIONS},
    locations=lambda section: section.option_locations,
)

DEPRECATED_ATTRIBUTES_ISSUES = DeprecatedOptions(
    issue_id=DEPRECATED_ATTRIBUTES_ISSUE_ID,
    blueprint_translation_key=DEPRECATED_ATTRIBUTES_BLUEPRINT_TRANSLATION_KEY,
    breaks_in_ha_version=DEPRECATED_ATTRIBUTES_BREAKS_IN,
    replacements=DEPRECATED_ATTRIBUTES,
    locations=lambda section: section.attribute_locations,
    parent_option=CONF_ATTRIBUTES,
    per_platform=True,
)


class CompositeDeviceIdRepairFlow(RepairsFlow):
    """Handler to select a device again after the linked device was split."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the flow."""
        self._entry_id = entry.entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of the fix flow."""
        # The flow manager passes {"issue_id": ...} as user_input to this step;
        # delegate so the form step can tell rendering from an (empty) submission
        return await self.async_step_select_device()

    async def async_step_select_device(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the device selection step."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="entry_removed")

        device_registry = dr.async_get(self.hass)
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input.get(CONF_DEVICE_ID)
            if (
                device_id is None
                or device_registry.async_get(
                    device_id,
                    include_composite_devices=False,
                )
                is not None
            ):
                options = {**entry.options}
                if device_id:
                    options[CONF_DEVICE_ID] = device_id
                else:
                    options.pop(CONF_DEVICE_ID, None)
                self.hass.config_entries.async_update_entry(entry, options=options)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_create_entry(data={})
            # A composite or unknown device id was submitted
            errors[CONF_DEVICE_ID] = "invalid_device"

        return self.async_show_form(
            step_id="select_device",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_DEVICE_ID,
                        description={
                            "suggested_value": entry.options.get(CONF_DEVICE_ID)
                        },
                    ): DeviceSelector(),
                }
            ),
            description_placeholders={"name": entry.title},
            errors=errors,
        )


def _format_deprecated_options(
    hass: HomeAssistant,
    deprecation: DeprecatedOptions,
    platform: Platform,
    deprecated: list[str],
    locations: dict[str, tuple[str, int]],
) -> str:
    """Return the deprecated options and their replacements as a markdown list."""
    prefix = f"{deprecation.parent_option}: " if deprecation.parent_option else ""
    changes: list[str] = []
    for key in deprecated:
        change = f"`{prefix}{key}` → `{deprecation.replacements[platform][key]}`"
        if (location := locations.get(key)) is not None:
            path = os.path.relpath(location[0], hass.config.config_dir)
            change = f"`{path}:{location[1]}`: {change}"
        changes.append(f"- {change}")
    return "\n".join(changes)


@callback
def _async_update_deprecated_options_issues(
    hass: HomeAssistant,
    config_sections: list[TemplateConfig] | None,
    deprecation: DeprecatedOptions,
) -> None:
    """Create an issue per entity or blueprint using deprecated options."""
    # Fingerprint to translation key, placeholders, platform and options of each entity
    issues: dict[str, tuple[str, dict[str, str], Platform, list[str]]] = {}
    for section in config_sections or []:
        blueprint_path: str | None = None
        if section.raw_blueprint_inputs is not None:
            blueprint_path = section.raw_blueprint_inputs[CONF_USE_BLUEPRINT][CONF_PATH]
        section_locations = deprecation.locations(section) or {}

        for platform, replacements in deprecation.replacements.items():
            for index, entity_config in enumerate(section.get(platform, [])):
                options = (
                    entity_config
                    if deprecation.parent_option is None
                    else entity_config.get(deprecation.parent_option)
                )
                # Attributes as a single template are blocked when rendered
                if not isinstance(options, dict):
                    continue
                deprecated = [key for key in options if key in replacements]
                if not deprecated:
                    continue

                platform_fingerprint: list[str] = []
                platform_placeholder: dict[str, str] = {}
                if deprecation.per_platform:
                    platform_fingerprint = [platform]
                    platform_placeholder = {"platform": platform.replace("_", " ")}

                # The id only changes with the configuration, so a dismissed issue
                # stays dismissed until the configuration changes
                if blueprint_path is not None:
                    # The fix belongs in the blueprint, one issue covers all its
                    # instances. Templates are left out, inputs can make them differ
                    # per instance
                    fingerprint = "\n".join(
                        [
                            *platform_fingerprint,
                            f"blueprint: {blueprint_path}",
                            *sorted(deprecated),
                        ]
                    )
                    if fingerprint in issues:
                        continue
                    translation_key = deprecation.blueprint_translation_key
                    label = {**platform_placeholder, "blueprint": blueprint_path}
                else:
                    fingerprint = "\n".join(
                        [
                            *platform_fingerprint,
                            tcv.entity_config_repair_identifier(
                                platform, entity_config, section.get(CONF_UNIQUE_ID)
                            ),
                            *(
                                f"{key}="
                                f"{getattr(options[key], 'template', options[key])}"
                                for key in sorted(deprecated)
                            ),
                        ]
                    )
                    translation_key = deprecation.issue_id
                    label = {
                        **platform_placeholder,
                        "identifier": tcv.entity_config_identifier(
                            platform, entity_config
                        ),
                    }

                # Identical entities share a fingerprint, one issue lists all of them
                issues.setdefault(fingerprint, (translation_key, label, platform, []))[
                    3
                ].append(
                    _format_deprecated_options(
                        hass,
                        deprecation,
                        platform,
                        deprecated,
                        section_locations[platform][index]
                        if platform in section_locations
                        else {},
                    )
                )

    with ir.async_refresh_issues(
        hass, DOMAIN, issue_id_pattern=f"{deprecation.issue_id}_"
    ) as refresh:
        for fingerprint, (translation_key, label, platform, options) in issues.items():
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"{deprecation.issue_id}_"
                f"{hashlib.sha256(fingerprint.encode()).hexdigest()[:16]}",
                breaks_in_ha_version=deprecation.breaks_in_ha_version,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=translation_key,
                translation_placeholders={**label, "options": "\n".join(options)},
                learn_more_url=(
                    "https://www.home-assistant.io/integrations/template/"
                    f"#{platform.replace('_', '-')}"
                ),
            )

        # Repairs of entities in invalid sections can't be told apart from stale
        # ones, keep them all so the ignore flag survives until the section is fixed
        if (
            isinstance(config_sections, TemplateConfigSections)
            and config_sections.has_invalid_sections
        ):
            refresh.async_cancel()


@callback
def async_update_deprecated_options_issues(
    hass: HomeAssistant, config_sections: list[TemplateConfig] | None
) -> None:
    """Create an issue per entity or blueprint using deprecated options."""
    for deprecation in (
        WEATHER_DEPRECATED_TEMPLATE_OPTIONS_ISSUES,
        DEPRECATED_ATTRIBUTES_ISSUES,
    ):
        _async_update_deprecated_options_issues(hass, config_sections, deprecation)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow."""
    if (
        issue_id.startswith("composite_device_id_")
        and data is not None
        and (entry := hass.config_entries.async_get_entry(str(data["entry_id"])))
        is not None
    ):
        return CompositeDeviceIdRepairFlow(entry)
    return ConfirmRepairFlow()
