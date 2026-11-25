"""Repairs platform for the template integration."""

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
from homeassistant.const import CONF_DEVICE_ID, CONF_PATH, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.selector import DeviceSelector

from . import validators as tcv
from .const import (
    DEPRECATED_TEMPLATE_OPTIONS,
    DOMAIN,
    DeprecatedTemplateOptions,
    TemplateConfig,
    TemplateConfigSections,
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


def format_deprecated_options(
    hass: HomeAssistant,
    deprecation: DeprecatedTemplateOptions,
    deprecated: list[str],
    locations: dict[str, tuple[str, int]],
) -> str:
    """Return the deprecated options and their replacements as a markdown list."""
    prefix = f"{deprecation.parent_option}: " if deprecation.parent_option else ""
    changes: list[str] = []
    for key in deprecated:
        if deprecation.requires_mapped_option:
            change = f"`{prefix}{key}` requires `{deprecation.options[key]}`"
        else:
            change = f"`{prefix}{key}` → `{deprecation.options[key]}`"
        if (location := locations.get(key)) is not None:
            path = os.path.relpath(location[0], hass.config.config_dir)
            change = f"`{path}:{location[1]}`: {change}"
        changes.append(f"- {change}")
    return "\n".join(changes)


@callback
def async_update_deprecated_template_options_issues(
    hass: HomeAssistant, config_sections: list[TemplateConfig] | None
) -> None:
    """Create the repairs of every platform with deprecated options."""
    for deprecation in DEPRECATED_TEMPLATE_OPTIONS:
        _async_update_deprecated_options_issues(hass, deprecation, config_sections)


@callback
def _async_update_deprecated_options_issues(
    hass: HomeAssistant,
    deprecation: DeprecatedTemplateOptions,
    config_sections: list[TemplateConfig] | None,
) -> None:
    """Create an issue per entity or blueprint of a platform using deprecated options."""
    platform = deprecation.platform
    # Fingerprint to translation key, label placeholder and options of each entity
    issues: dict[str, tuple[str, dict[str, str], list[str]]] = {}
    for section in config_sections or []:
        blueprint_path: str | None = None
        if section.raw_blueprint_inputs is not None:
            blueprint_path = section.raw_blueprint_inputs[CONF_USE_BLUEPRINT][CONF_PATH]

        for index, entity_config in enumerate(section.get(platform, [])):
            if not (deprecated := deprecation.deprecated_options(entity_config)):
                continue

            # The id only changes with the configuration, so a dismissed issue stays
            # dismissed until the configuration changes
            if blueprint_path is not None:
                # The fix belongs in the blueprint, one issue covers all its instances.
                # Templates are left out, inputs can make them differ per instance
                fingerprint = "\n".join(
                    [f"blueprint: {blueprint_path}", *sorted(deprecated)]
                )
                if fingerprint in issues:
                    continue
                translation_key = deprecation.blueprint_translation_key
                label = {"blueprint": blueprint_path}
            else:
                options_config = deprecation.options_config(entity_config)
                fingerprint = "\n".join(
                    [
                        tcv.entity_config_repair_identifier(
                            platform, entity_config, section.get(CONF_UNIQUE_ID)
                        ),
                        *(
                            f"{key}="
                            f"{getattr(options_config[key], 'template', options_config[key])}"
                            for key in sorted(deprecated)
                        ),
                    ]
                )
                translation_key = deprecation.translation_key
                label = {
                    "identifier": tcv.entity_config_identifier(platform, entity_config)
                }

            # Identical entities share a fingerprint, one issue lists all of them
            issues.setdefault(fingerprint, (translation_key, label, []))[2].append(
                format_deprecated_options(
                    hass,
                    deprecation,
                    deprecated,
                    section.option_locations[platform][index]
                    if section.option_locations
                    else {},
                )
            )

    with ir.async_refresh_issues(
        hass, DOMAIN, issue_id_pattern=f"{deprecation.translation_key}_"
    ) as refresh:
        for fingerprint, (translation_key, label, options) in issues.items():
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"{deprecation.translation_key}_"
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
