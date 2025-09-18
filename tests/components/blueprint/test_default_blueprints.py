"""Test default blueprints."""

import importlib
import logging
import pathlib

import pytest

from homeassistant.components.blueprint import BLUEPRINT_SCHEMA, models
from homeassistant.components.blueprint.const import BLUEPRINT_FOLDER
from homeassistant.util import yaml as yaml_util

DOMAINS = ["automation"]
LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize("domain", DOMAINS)
def test_default_blueprints(domain: str) -> None:
    """Validate a folder of blueprints."""
    integration = importlib.import_module(f"homeassistant.components.{domain}")
    blueprint_folder = pathlib.Path(integration.__file__).parent / BLUEPRINT_FOLDER
    items = list(blueprint_folder.glob("*"))
    assert len(items) > 0, "Folder cannot be empty"

    for fil in items:
        LOGGER.info("Processing %s", fil)
        assert fil.name.endswith(".yaml")
        data = yaml_util.load_yaml(fil)
        models.Blueprint(data, expected_domain=domain, schema=BLUEPRINT_SCHEMA)
