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

    entries = hass.config_entries.async_entries(DOMAIN, include_ignore=False)
    if not entries:
        _async_create_issue(
            hass,
            f"deprecated_yaml_import_issue_no_gateway_{platform}",
            "deprecated_yaml_import_issue_no_gateway",
            {"platform": platform},
        )
        return

    entry = entries[0]
    data = {CONF_ID: address, CONF_DEVICE_TYPE_ID: device_type_id, **options}
    stored = next(
        (
            subentry
            for subentry in entry.subentries.values()
            if subentry.unique_id == address
        ),
        None,
    )
    if stored is None:
        subentry = ConfigSubentry(
            data=MappingProxyType(data),
            subentry_type=SUBENTRY_TYPE_DEVICE,
            title=name,
            unique_id=address,
        )
        hass.config_entries.async_add_subentry(entry, subentry)
    elif stored.data != data:
        # A device is stored once: a second YAML entry with the same ID and other
        # settings, which used to be an entity of its own, cannot be imported.
        _async_create_issue(
            hass,
            f"deprecated_yaml_import_issue_already_configured_{platform}_{name}",
            "deprecated_yaml_import_issue_already_configured",
            {"platform": platform, "name": name, "id": address},
        )
        return

    _async_create_issue(
        hass, f"deprecated_yaml_{platform}", "deprecated_yaml", {"platform": platform}
    )
