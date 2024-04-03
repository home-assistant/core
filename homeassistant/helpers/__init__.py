"""Helper methods for components within Home Assistant."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .typing import ConfigType


def config_per_platform(
    config: ConfigType, domain: str
) -> Iterable[tuple[str | None, ConfigType]]:
    """Break a component config into different platforms.

    For example, will find 'switch', 'switch 2', 'switch 3', .. etc
    Async friendly.
    """
    # pylint: disable-next=import-outside-toplevel
    from homeassistant import config as ha_config

    # pylint: disable-next=import-outside-toplevel
    from .deprecation import _print_deprecation_warning

    _print_deprecation_warning(
        config_per_platform,
        "config.config_per_platform",
        "function",
        "called",
        "2024.6",
    )
    return ha_config.config_per_platform(config, domain)


config_per_platform.__name__ = "helpers.config_per_platform"


def extract_domain_configs(config: ConfigType, domain: str) -> Sequence[str]:
    """Extract keys from config for given domain name.

    Async friendly.
    """
    # pylint: disable-next=import-outside-toplevel
    from homeassistant import config as ha_config

    # pylint: disable-next=import-outside-toplevel
    from .deprecation import _print_deprecation_warning

    _print_deprecation_warning(
        extract_domain_configs,
        "config.extract_domain_configs",
        "function",
        "called",
        "2024.6",
    )
    return ha_config.extract_domain_configs(config, domain)


extract_domain_configs.__name__ = "helpers.extract_domain_configs"
