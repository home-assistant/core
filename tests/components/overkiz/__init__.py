"""Tests for the overkiz component."""

import logging

import humps
from pyoverkiz.models import Setup

from homeassistant.components.overkiz.const import DOMAIN

from tests.common import load_json_object_fixture

DEFAULT_SETUP_FIXTURE = "setup/setup_tahoma_switch.json"
LOGGER = logging.getLogger(__name__)


def load_setup_fixture(fixture: str = DEFAULT_SETUP_FIXTURE) -> Setup:
    """Return setup from fixture."""
    setup_json = load_json_object_fixture(fixture, DOMAIN)
    return Setup(**humps.decamelize(setup_json))
