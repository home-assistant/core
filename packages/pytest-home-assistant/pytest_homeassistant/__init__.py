"""Home Assistant pytest fixtures and test helpers."""

import pytest

# Preserve assertion introspection when helpers are imported through compatibility modules.
pytest.register_assert_rewrite(
    "pytest_homeassistant.common",
    "pytest_homeassistant.plugins",
    "pytest_homeassistant.components.common",
    "pytest_homeassistant.components.diagnostics",
    "pytest_homeassistant.components.infrared.common",
    "pytest_homeassistant.components.mqtt.common",
    "pytest_homeassistant.components.radio_frequency.common",
    "pytest_homeassistant.components.recorder.common",
    "pytest_homeassistant.components.repairs",
)
