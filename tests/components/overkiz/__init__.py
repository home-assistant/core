"""Tests for the overkiz component."""

import humps
from pyoverkiz.models import Setup

from tests.common import load_json_object_fixture


def load_setup_fixture(
    fixture: str = "overkiz/setup_tahoma_switch.json",
) -> Setup:
    """Return setup from fixture."""
    setup_json = load_json_object_fixture(fixture)
    return Setup(**humps.decamelize(setup_json))
