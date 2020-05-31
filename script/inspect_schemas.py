#!/usr/bin/env python3
"""Inspect all component SCHEMAS."""
import importlib
import os
import pkgutil

from homeassistant.config import _identify_config_schema
from homeassistant.scripts.check_config import color


def explore_module(package):
    """Explore the modules."""
    module = importlib.import_module(package)
    if not hasattr(module, "__path__"):
        return []
    for _, name, _ in pkgutil.iter_modules(module.__path__, f"{package}."):
        yield name


def main():
    """Run the script."""
    if not os.path.isfile("requirements_all.txt"):
        print("Run this from HA root dir")
        return

    msg = {}

    def add_msg(key, item):
        """Add a message."""
        if key not in msg:
            msg[key] = []
        msg[key].append(item)

    for package in explore_module("homeassistant.components"):
        module = importlib.import_module(package)
        module_name = getattr(module, "DOMAIN", module.__name__)

        if hasattr(module, "PLATFORM_SCHEMA"):
            if hasattr(module, "CONFIG_SCHEMA"):
                add_msg(
                    "WARNING",
                    f"Module {module_name} contains PLATFORM and CONFIG schemas",
                )
            add_msg("PLATFORM SCHEMA", module_name)
            continue

        if not hasattr(module, "CONFIG_SCHEMA"):
            add_msg("NO SCHEMA", module_name)
            continue

        schema_type, schema = _identify_config_schema(module)

        add_msg(
            f"CONFIG_SCHEMA {schema_type}",
            f"{module_name} {color('cyan', str(schema)[:60])}",
        )

    for key in sorted(msg):
        print("\n{}\n - {}".format(key, "\n - ".join(msg[key])))


if __name__ == "__main__":
    main()
