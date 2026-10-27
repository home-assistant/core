"""Validate LoRaWAN manifest registrations and generated discovery data."""

import ast
import json
from pathlib import Path

import probatio
import pytest

from script.hassfest.lorawan import generate_and_validate
from script.hassfest.manifest import INTEGRATION_MANIFEST_SCHEMA
from script.hassfest.model import Config, Integration
from script.hassfest.quality_scale_validation import discovery


@pytest.mark.parametrize(
    "vendors",
    [
        [],
        [744],
        [["chirpstack", -1]],
        [["chirpstack", 744], ["chirpstack", 744]],
        [["", 744]],
        [["tts", ""]],
        [["tts", True]],
        [["tts"]],
    ],
)
def test_invalid_vendor_ids(vendors: list[object]) -> None:
    """Discovery identities must be unique stack and native brand pairs."""
    manifest = json.loads(
        Path("homeassistant/components/lorawan/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    manifest["lorawan"] = vendors
    with pytest.raises(probatio.Invalid):
        INTEGRATION_MANIFEST_SCHEMA(manifest)


def test_stack_specific_vendor_ids() -> None:
    """Native numeric and string brand IDs survive manifest validation."""
    manifest = json.loads(
        Path("homeassistant/components/lorawan/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    manifest["lorawan"] = [["chirpstack", 744], ["tts", "sensecap"]]
    assert INTEGRATION_MANIFEST_SCHEMA(manifest)["lorawan"] == [
        ("chirpstack", 744),
        ("tts", "sensecap"),
    ]


@pytest.mark.parametrize(
    ("missing", "error_count"),
    [
        ("dependencies", 1),
        ("config_flow", 1),
        (None, 0),
    ],
)
def test_registration_requirements(
    tmp_path: Path,
    config: Config,
    missing: str | None,
    error_count: int,
) -> None:
    """A discovered integration needs a config flow and lorawan dependency."""
    path = tmp_path / "vendor"
    path.mkdir()
    manifest = {
        "domain": "vendor",
        "lorawan": [["chirpstack", 744], ["tts", "sensecap"]],
        "dependencies": ["lorawan"],
        "config_flow": True,
    }
    manifest.pop(missing, None)
    integration = Integration(path, _config=config, _manifest=manifest)
    source = generate_and_validate({"vendor": integration})
    registration = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "LORAWAN"
    )
    assert ast.literal_eval(registration.value) == {
        "vendor": [("chirpstack", 744), ("tts", "sensecap")]
    }
    assert len(integration.errors) == error_count


def test_discovery_quality_rule(tmp_path: Path, config: Config) -> None:
    """The LoRaWAN manifest hook satisfies HA's discovery quality rule."""
    (tmp_path / "config_flow.py").write_text("# Config flow is validated separately.\n")
    integration = Integration(
        tmp_path, _config=config, _manifest={"lorawan": [["chirpstack", 744]]}
    )
    assert discovery.validate(config, integration, rules_done={"discovery"}) is None
