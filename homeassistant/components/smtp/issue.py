"""Issues for SMTP integration."""

from typing import Any

from homeassistant.const import CONF_NAME, CONF_SENDER
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    create_issue,
)
from homeassistant.util import yaml as yaml_util

from .const import CONF_SERVER, DOMAIN


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
                "integration_title": "SMTP",
            },
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            (
                f"deprecated_yaml_import_issue_error_{config.get(CONF_NAME, 'unknown')}"
                f"_{config[CONF_SENDER]}_{config[CONF_SERVER]}"
            ),
            breaks_in_ha_version="2027.1.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue_error",
            translation_placeholders={
                "url": f"/config/integrations/dashboard/add?domain={DOMAIN}",
                "config": yaml_util.dump(config),
            },
        )


@callback
def deprecated_notify_action_call(hass: HomeAssistant, service_name: str) -> None:
    """Deprecated action call."""

    create_issue(
        hass,
        DOMAIN,
        f"deprecated_notify_action_{service_name}",
        breaks_in_ha_version="2027.3.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_notify_action",
        translation_placeholders={
            "action": f"notify.{service_name}",
            "new_action_1": "notify.send_message",
            "new_action_2": "smtp.send_message",
            "example_yaml_1": """
```yaml
action: notify.send_message
target:
  entity_id: notify.recipient
data:
  message: Hello World
  title: Hello
```
""",
            "example_yaml_2": """
```yaml
action: smtp.send_message
target:
    entity_id: notify.recipient
data:
  title: Hello
  message: Hello World
  html: <html><body>Hello World<br><img src="cid:snapshot"></body></html>
  attachments:
    - attachment:
        media_content_id: media-source://camera/camera.demo_camera
        media_content_type: application/vnd.apple.mpegurl
      filename: snapshot.jpg
      content_id: snapshot
```
""",
        },
    )
