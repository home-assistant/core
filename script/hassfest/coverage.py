"""Validate coverage files."""
from __future__ import annotations

from pathlib import Path

from .model import Config, Integration

DONT_IGNORE = (
    "config_flow.py",
    "device_action.py",
    "device_condition.py",
    "device_trigger.py",
    "group.py",
    "intent.py",
    "logbook.py",
    "media_source.py",
    "scene.py",
)

# They were violating when we introduced this check
# Need to be fixed in a future PR.
ALLOWED_IGNORE_VIOLATIONS = {
    ("ambient_station", "config_flow.py"),
    ("cast", "config_flow.py"),
    ("daikin", "config_flow.py"),
    ("doorbird", "config_flow.py"),
    ("doorbird", "logbook.py"),
    ("elkm1", "config_flow.py"),
    ("elkm1", "scene.py"),
    ("fibaro", "scene.py"),
    ("flume", "config_flow.py"),
    ("hangouts", "config_flow.py"),
    ("harmony", "config_flow.py"),
    ("hisense_aehw4a1", "config_flow.py"),
    ("home_connect", "config_flow.py"),
    ("huawei_lte", "config_flow.py"),
    ("ifttt", "config_flow.py"),
    ("ios", "config_flow.py"),
    ("iqvia", "config_flow.py"),
    ("knx", "scene.py"),
    ("konnected", "config_flow.py"),
    ("lcn", "scene.py"),
    ("life360", "config_flow.py"),
    ("lifx", "config_flow.py"),
    ("lutron", "scene.py"),
    ("mobile_app", "config_flow.py"),
    ("nest", "config_flow.py"),
    ("plaato", "config_flow.py"),
    ("point", "config_flow.py"),
    ("rachio", "config_flow.py"),
    ("sense", "config_flow.py"),
    ("sms", "config_flow.py"),
    ("solarlog", "config_flow.py"),
    ("somfy", "config_flow.py"),
    ("sonos", "config_flow.py"),
    ("speedtestdotnet", "config_flow.py"),
    ("spider", "config_flow.py"),
    ("starline", "config_flow.py"),
    ("tado", "config_flow.py"),
    ("tahoma", "scene.py"),
    ("totalconnect", "config_flow.py"),
    ("tradfri", "config_flow.py"),
    ("tuya", "config_flow.py"),
    ("tuya", "scene.py"),
    ("upnp", "config_flow.py"),
    ("velux", "scene.py"),
    ("wemo", "config_flow.py"),
    ("wiffi", "config_flow.py"),
    ("wink", "scene.py"),
}


def validate(integrations: dict[str, Integration], config: Config):
    """Validate coverage."""
    coverage_path = config.root / ".coveragerc"

    not_found = []
    checking = False

    with coverage_path.open("rt") as fp:
        for line in fp:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if not checking:
                if line == "omit =":
                    checking = True
                continue

            # Finished
            if line == "[report]":
                break

            path = Path(line)

            # Discard wildcard
            path_exists = path
            while "*" in path_exists.name:
                path_exists = path_exists.parent

            if not path_exists.exists():
                not_found.append(line)
                continue

            if (
                not line.startswith("homeassistant/components/")
                or len(path.parts) != 4
                or path.parts[-1] != "*"
            ):
                continue

            integration_path = path.parent

            integration = integrations[integration_path.name]

            for check in DONT_IGNORE:
                if (integration_path.name, check) in ALLOWED_IGNORE_VIOLATIONS:
                    continue

                if (integration_path / check).exists():
                    integration.add_error(
                        "coverage",
                        f"{check} must not be ignored by the .coveragerc file",
                    )

    if not not_found:
        return

    errors = []

    if not_found:
        errors.append(
            f".coveragerc references files that don't exist: {', '.join(not_found)}."
        )

    raise RuntimeError(" ".join(errors))
