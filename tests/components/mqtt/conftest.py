"""Test fixtures for mqtt component."""
from collections.abc import Generator

import pytest

from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def patch_hass_config(
    hass: HomeAssistant, mock_hass_config: None, hass_config: ConfigType
) -> Generator[None, None, None]:
    """Patch configuration.yaml."""
    hass.config_entries = ConfigEntries(
        hass,
        hass_config
        or {
            "_": (
                "Not empty or else some bad checks for hass config in discovery.py"
                " breaks"
            )
        },
    )

    return
