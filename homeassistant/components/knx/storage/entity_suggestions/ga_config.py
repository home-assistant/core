"""Group address configs of `knx` entity configurations."""

from typing import Any

from ..const import CONF_GA_PASSIVE, CONF_GA_STATE, CONF_GA_WRITE

type ConfigPath = tuple[str, ...]


def iter_ga_configs(
    config: dict[str, Any], path: ConfigPath = ()
) -> list[tuple[ConfigPath, dict[str, Any]]]:
    """Return the group address configs of a `knx` config with their path."""
    ga_configs: list[tuple[ConfigPath, dict[str, Any]]] = []
    for key, value in config.items():
        if not isinstance(value, dict):
            continue
        if any(
            slot in value for slot in (CONF_GA_WRITE, CONF_GA_STATE, CONF_GA_PASSIVE)
        ):
            ga_configs.append(((*path, key), value))
        else:
            # a section or the chosen option of a group select
            ga_configs.extend(iter_ga_configs(value, (*path, key)))
    return ga_configs
