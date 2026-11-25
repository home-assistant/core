"""Test fixtures for device tracker tests."""

import pytest

from tests.components.zone.common import improved_presence_detection  # noqa: F401


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Use temporary config directory for device_tracker tests.

    This fixture can be removed when the legacy YAML writing has been removed
    from the device tracker integration.
    """
    return hass_tmp_config_dir
