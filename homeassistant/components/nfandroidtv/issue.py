"""Issues for the Notifications for Android TV / Fire TV integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, create_issue

from .const import DOMAIN


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
            "new_action_2": "nfandroidtv.send_message",
            "example_yaml_1": """
```yaml
action: notify.send_message
target:
  entity_id: notify.my_tv
data:
  message: Hello World
  title: Hello
```
""",
            "example_yaml_2": """
```yaml
action: nfandroidtv.send_message
target:
    entity_id: notify.my_tv
data:
  title: Hello
  message: World!
  image:
    media_content_id: media-source://camera/camera.demo_camera
    media_content_type: application/vnd.apple.mpegurl
  icon:
    media_content_id: media-source://image/image.demo
    media_content_type: image/png
  position: center
  duration:
    seconds: 20
  interactive: true
  background_color: pink
  fontsize: medium
  transparency: 50%
```
""",
        },
    )
