"""Issues for the Free Mobile integration."""

from typing import Any

from homeassistant.const import CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util import yaml as yaml_util

from .const import DOMAIN


@callback
def async_deprecate_yaml_issue(
    hass: HomeAssistant, config: dict[str, Any], *, import_success: bool = True
) -> None:
    """Deprecate yaml issue."""
    if import_success:
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            breaks_in_ha_version="2027.1.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Free Mobile",
            },
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_error_{config[CONF_USERNAME]}",
            breaks_in_ha_version="2027.2.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue_error",
            translation_placeholders={
                "url": f"/config/integrations/dashboard/add?domain={DOMAIN}",
                "config": yaml_util.dump(config),
            },
        )
