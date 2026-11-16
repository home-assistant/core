"""Import of EnOcean devices configured in YAML into the config entry."""

from types import MappingProxyType
from typing import Any

from enocean_async.address import Address

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import CONF_DEVICE_TYPE_ID, DOMAIN, SUBENTRY_TYPE_DEVICE

BREAKS_IN_HA_VERSION = "2027.6.0"


@callback
def _async_create_issue(
    hass: HomeAssistant,
    issue_id: str,
    translation_key: str,
    translation_placeholders: dict[str, str],
) -> None:
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders=translation_placeholders,
    )


@callback
def async_import_yaml_device(
    hass: HomeAssistant,
    platform: Platform,
    dev_id: list[int],
    name: str,
    device_type_id: str,
    options: dict[str, Any],
) -> None:
    """Add a device configured in YAML to the config entry.

    A repair issue tells the user to remove the YAML, or why the device could
    not be imported.
    """
    try:
        address = str(Address(dev_id))
    except ValueError:
        _async_create_issue(
            hass,
            f"deprecated_yaml_import_issue_invalid_id_{platform}_{name}",
            "deprecated_yaml_import_issue_invalid_id",
            {"platform": platform, "name": name},
        )
        return

    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        _async_create_issue(
            hass,
            f"deprecated_yaml_import_issue_no_gateway_{platform}",
            "deprecated_yaml_import_issue_no_gateway",
            {"platform": platform},
        )
        return

    entry = entries[0]
    if all(subentry.unique_id != address for subentry in entry.subentries.values()):
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(
                    {CONF_ID: address, CONF_DEVICE_TYPE_ID: device_type_id, **options}
                ),
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title=name,
                unique_id=address,
            ),
        )

    _async_create_issue(
        hass, f"deprecated_yaml_{platform}", "deprecated_yaml", {"platform": platform}
    )
