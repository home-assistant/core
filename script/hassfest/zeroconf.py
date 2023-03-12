"""Generate zeroconf file."""
from __future__ import annotations

from collections import defaultdict

from homeassistant.loader import (
    async_process_zeroconf_match_dict,
    homekit_always_discover,
)

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate zeroconf data."""
    service_type_dict = defaultdict(list)
    homekit_dict: dict[str, dict[str, str]] = {}

    for domain in sorted(integrations):
        integration = integrations[domain]
        service_types = integration.manifest.get("zeroconf", [])
        homekit = integration.manifest.get("homekit", {})
        homekit_models = homekit.get("models", [])

        if not (service_types or homekit_models):
            continue

        for entry in service_types:
            data = {"domain": domain}
            if isinstance(entry, dict):
                typ = entry["type"]
                data.update(async_process_zeroconf_match_dict(entry))
            else:
                typ = entry

            service_type_dict[typ].append(data)

        for model in homekit_models:
            if model in homekit_dict:
                integration.add_error(
                    "zeroconf",
                    f"Integrations {domain} and {homekit_dict[model]} "
                    "have overlapping HomeKit models",
                )
                break

            homekit_dict[model] = {
                "domain": domain,
                "always_discover": homekit_always_discover(
                    integration.manifest["iot_class"]
                ),
            }

    # HomeKit models are matched on starting string, make sure none overlap.
    warned = set()
    for key in homekit_dict:
        if key in warned:
            continue

        # n^2 yoooo
        for key_2 in homekit_dict:
            if key == key_2 or key_2 in warned:
                continue

            if key.startswith(key_2) or key_2.startswith(key):
                integration.add_error(
                    "zeroconf",
                    f"Integrations {homekit_dict[key]} and {homekit_dict[key_2]} "
                    "have overlapping HomeKit models",
                )
                warned.add(key)
                warned.add(key_2)
                break

    return format_python_namespace(
        {
            "HOMEKIT": {key: homekit_dict[key] for key in homekit_dict},
            "ZEROCONF": {key: service_type_dict[key] for key in service_type_dict},
        }
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate zeroconf file."""
    zeroconf_path = config.root / "homeassistant/generated/zeroconf.py"
    config.cache["zeroconf"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    with open(str(zeroconf_path)) as fp:
        current = fp.read()
        if current != content:
            config.add_error(
                "zeroconf",
                "File zeroconf.py is not up to date. Run python3 -m script.hassfest",
                fixable=True,
            )
        return


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate zeroconf file."""
    zeroconf_path = config.root / "homeassistant/generated/zeroconf.py"
    with open(str(zeroconf_path), "w") as fp:
        fp.write(f"{config.cache['zeroconf']}")
