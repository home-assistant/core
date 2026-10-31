"""Home Assistant pytest fixtures and test helpers."""

import pytest

# Install Home Assistant's httpx and voluptuous aliases before test dependencies.
import homeassistant  # noqa: F401

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
