"""Issues for the deprecated Kodi YAML notify platform."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN, SERVICE_NOTIFY
from homeassistant.config import config_per_platform
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.hass_dict import HassKey

from .const import DEFAULT_PORT, DOMAIN

BREAKS_IN_HA_VERSION = "2027.6.0"
KODI_DOCS_URL = "https://www.home-assistant.io/integrations/kodi/"


@dataclass(frozen=True, slots=True)
class YamlNotifyConfig:
    """A Kodi notify platform configured in YAML."""

    name: str | None
    host: str
    port: int
    username: str | None
    password: str | None

    @property
    def service_name(self) -> str:
        """Return the name of the legacy notify action, as the notify loader sets it."""
        return slugify(self.name or SERVICE_NOTIFY)

    def matches(self, data: Mapping[str, Any]) -> bool:
        """Return if a config entry is for the same Kodi host, port and credentials."""
        return (
            data[CONF_HOST] == self.host
            and data[CONF_PORT] == self.port
            and (data.get(CONF_USERNAME) or None) == self.username
            and (data.get(CONF_PASSWORD) or None) == self.password
        )


DATA_YAML_NOTIFY: HassKey[list[YamlNotifyConfig]] = HassKey(f"{DOMAIN}_yaml_notify")


def _optional_str(value: Any) -> str | None:
    """Return a YAML value as the notify schema reads it, with empty values as None."""
    return str(value) if value not in (None, "") else None


@callback
def async_get_yaml_notify_configs(config: ConfigType) -> list[YamlNotifyConfig]:
    """Return the Kodi notify platforms configured in YAML."""
    yaml_configs: list[YamlNotifyConfig] = []
    # Not validated yet: the notify integration validates and reports these blocks
    for platform, p_config in config_per_platform(config, NOTIFY_DOMAIN):
        if platform != DOMAIN or not isinstance(p_config, dict):
            continue
        if (host := _optional_str(p_config.get(CONF_HOST))) is None:
            continue
        try:
            port = int(p_config.get(CONF_PORT, DEFAULT_PORT))
        except TypeError, ValueError:
            continue
        if host.startswith(("http://", "https://")):
            host = host[host.index("://") + 3 :]
        yaml_configs.append(
            YamlNotifyConfig(
                name=_optional_str(p_config.get(CONF_NAME)),
                host=host,
                port=port,
                username=_optional_str(p_config.get(CONF_USERNAME)),
                password=_optional_str(p_config.get(CONF_PASSWORD)),
            )
        )
    return yaml_configs


@callback
def async_create_notify_entity_issue(
    hass: HomeAssistant, yaml_config: YamlNotifyConfig, entity_id: str, title: str
) -> None:
    """Create an issue for a YAML notify platform that has a replacement entity."""
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_notify_{yaml_config.service_name}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml_notify_entity",
        translation_placeholders={
            "action": f"{NOTIFY_DOMAIN}.{yaml_config.service_name}",
            "entity_id": entity_id,
            "title": title,
        },
    )


@callback
def async_create_no_entry_issue(
    hass: HomeAssistant, yaml_config: YamlNotifyConfig
) -> None:
    """Create an issue for a YAML notify platform without a matching config entry."""
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_notify_{yaml_config.service_name}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml_notify_no_entry",
        translation_placeholders={
            "action": f"{NOTIFY_DOMAIN}.{yaml_config.service_name}",
            "url": KODI_DOCS_URL,
        },
    )
