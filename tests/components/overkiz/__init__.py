"""Tests for the Overkiz component."""

from pyoverkiz.converter import converter
from pyoverkiz.models import Setup
from pytest_homeassistant.common import load_json_object_fixture

from homeassistant.components.overkiz.const import DOMAIN

DEFAULT_SETUP_FIXTURE = "setup/cloud_somfy_tahoma_switch_europe.json"


def load_setup_fixture(fixture: str = DEFAULT_SETUP_FIXTURE) -> Setup:
    """Return setup from fixture."""
    setup_json = load_json_object_fixture(fixture, DOMAIN)
    return converter.structure(setup_json, Setup)
