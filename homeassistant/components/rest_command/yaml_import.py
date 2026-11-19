"""Import of REST commands from YAML into the config entry."""

from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_IMPORT,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import CONF_HEADERS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.template import Template

from .const import CONF_ACTION, DOMAIN, SUBENTRY_TYPE_COMMAND


def _to_storable(command_config: dict[str, Any]) -> dict[str, Any]:
    """Turn a validated YAML command back into plain values."""
    data: dict[str, Any] = {}
    for key, value in command_config.items():
        if isinstance(value, Template):
            data[key] = value.template
        elif key == CONF_HEADERS:
            data[key] = {name: header.template for name, header in value.items()}
        else:
            data[key] = value
    return data


@callback
def async_import_yaml_commands(
    hass: HomeAssistant, commands: dict[str, dict[str, Any]]
) -> None:
    """Copy the commands from YAML that are not imported yet into the entry."""
    if not commands:
        return

    subentries = [
        ConfigSubentryData(
            data={CONF_ACTION: name, **_to_storable(command_config)},
            subentry_type=SUBENTRY_TYPE_COMMAND,
            title=name,
            unique_id=name,
        )
        for name, command_config in commands.items()
    ]

    if entries := hass.config_entries.async_entries(DOMAIN, include_ignore=True):
        entry = entries[0]
        if entry.source == SOURCE_IGNORE:
            return
        imported = {subentry.unique_id for subentry in entry.subentries.values()}
        for subentry in subentries:
            if subentry["unique_id"] in imported:
                continue
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(subentry["data"]),
                    subentry_type=subentry["subentry_type"],
                    title=subentry["title"],
                    unique_id=subentry["unique_id"],
                ),
            )
    else:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={"subentries": subentries},
            ),
            eager_start=True,
        )

    ir.async_create_issue(
        hass,
        DOMAIN,
        "yaml_imported",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="yaml_imported",
    )
