"""Issues for the deprecated Kodi YAML notify platform."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import probatio

from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    SERVICE_NOTIFY,
)
from homeassistant.config import config_per_platform
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROXY_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.hass_dict import HassKey

from .const import DEFAULT_PORT, DOMAIN

BREAKS_IN_HA_VERSION = "2027.6.0"
KODI_DOCS_URL = "https://www.home-assistant.io/integrations/kodi/"

DEFAULT_PROXY_SSL = False

# Schema of the legacy notify platform, used by notify.py and to read the YAML
YAML_NOTIFY_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(CONF_PROXY_SSL, default=DEFAULT_PROXY_SSL): cv.boolean,
        probatio.Inclusive(CONF_USERNAME, "auth"): cv.string,
        probatio.Inclusive(probatio.Secret(CONF_PASSWORD), "auth"): cv.string,
    }
)


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


@callback
def async_get_yaml_notify_configs(config: ConfigType) -> list[YamlNotifyConfig]:
    """Return the valid Kodi notify platforms configured in YAML."""
    yaml_configs: list[YamlNotifyConfig] = []
    for platform, p_config in config_per_platform(config, NOTIFY_DOMAIN):
        if platform != DOMAIN:
            continue
        # Not validated yet; the notify integration reports invalid blocks
        try:
            validated = YAML_NOTIFY_SCHEMA(p_config)
        except probatio.Invalid:
            continue
        host: str = validated[CONF_HOST]
        if host.startswith(("http://", "https://")):
            host = host[host.index("://") + 3 :]
        yaml_configs.append(
            YamlNotifyConfig(
                name=validated.get(CONF_NAME) or None,
                host=host,
                port=validated[CONF_PORT],
                username=validated.get(CONF_USERNAME) or None,
                password=validated.get(CONF_PASSWORD) or None,
            )
        )
    return yaml_configs


@callback
def _async_create_issue(
    hass: HomeAssistant,
    yaml_config: YamlNotifyConfig,
    translation_key: str,
    placeholders: dict[str, str],
) -> None:
    """Create the deprecation issue of a YAML notify platform."""
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_notify_{yaml_config.service_name}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders={
            "action": f"{NOTIFY_DOMAIN}.{yaml_config.service_name}",
            **placeholders,
        },
    )


@callback
def async_create_notify_entity_issue(
    hass: HomeAssistant, yaml_config: YamlNotifyConfig, entity_id: str, title: str
) -> None:
    """Create an issue for a YAML notify platform that has a replacement entity."""
    _async_create_issue(
        hass,
        yaml_config,
        "deprecated_yaml_notify_entity",
        {"entity_id": entity_id, "title": title},
    )


@callback
def async_create_entry_disabled_issue(
    hass: HomeAssistant, yaml_config: YamlNotifyConfig, title: str
) -> None:
    """Create an issue for a YAML notify platform whose matching entry is disabled."""
    _async_create_issue(
        hass, yaml_config, "deprecated_yaml_notify_entry_disabled", {"title": title}
    )


@callback
def async_create_no_entry_issue(
    hass: HomeAssistant, yaml_config: YamlNotifyConfig
) -> None:
    """Create an issue for a YAML notify platform without a matching config entry."""
    _async_create_issue(
        hass, yaml_config, "deprecated_yaml_notify_no_entry", {"url": KODI_DOCS_URL}
    )
