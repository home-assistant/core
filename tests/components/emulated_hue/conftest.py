"""Conftest for emulated_hue tests."""

import pytest

from homeassistant.components.emulated_hue.config import Config


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture(autouse=True)
def reset_config_cache() -> None:
    """Reset config cache."""
    Config.entity_id_to_number.cache_clear()
