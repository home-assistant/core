"""Helper methods for components within Home Assistant."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
import re
from typing import TYPE_CHECKING

from homeassistant.const import CONF_PLATFORM

if TYPE_CHECKING:
    from .typing import ConfigType


def config_per_platform(
    config: ConfigType, domain: str
) -> Iterable[tuple[str | None, ConfigType]]:
    """Break a component config into different platforms.

    For example, will find 'switch', 'switch 2', 'switch 3', .. etc
    Async friendly.
    """
    for config_key in extract_domain_configs(config, domain):
        if not (platform_config := config[config_key]):
            continue

        if not isinstance(platform_config, list):
            platform_config = [platform_config]

        item: ConfigType
        platform: str | None
        for item in platform_config:
            try:
                platform = item.get(CONF_PLATFORM)
            except AttributeError:
                platform = None

            yield platform, item


def extract_domain_configs(config: ConfigType, domain: str) -> Sequence[str]:
    """Extract keys from config for given domain name.

    Async friendly.
    """
    pattern = re.compile(rf"^{domain}(| .+)$")
    return [key for key in config.keys() if pattern.match(key)]
