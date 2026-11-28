"""Telegram platform for notify component."""

import probatio

from homeassistant.components.notify import PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DOMAIN = "telegram"

CONF_CHAT_ID = "chat_id"

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {probatio.Required(CONF_CHAT_ID): probatio.Coerce(int)}
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Get the Telegram notification service."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        DOMAIN,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="integration_removed",
        translation_placeholders={
            CONF_URL: "https://www.home-assistant.io/integrations/telegram_bot#notifiers"
        },
    )
