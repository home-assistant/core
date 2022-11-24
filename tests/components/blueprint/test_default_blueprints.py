"""Test default blueprints."""
import importlib
import logging
import pathlib

import pytest

from spencerassistant.components.blueprint import models
from spencerassistant.components.blueprint.const import BLUEPRINT_FOLDER
from spencerassistant.util import yaml

DOMAINS = ["automation"]
LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize("domain", DOMAINS)
def test_default_blueprints(domain: str):
    """Validate a folder of blueprints."""
    integration = importlib.import_module(f"spencerassistant.components.{domain}")
    blueprint_folder = pathlib.Path(integration.__file__).parent / BLUEPRINT_FOLDER
    items = list(blueprint_folder.glob("*"))
    assert len(items) > 0, "Folder cannot be empty"

    for fil in items:
        LOGGER.info("Processing %s", fil)
        assert fil.name.endswith(".yaml")
        data = yaml.load_yaml(fil)
        models.Blueprint(data, expected_domain=domain)
