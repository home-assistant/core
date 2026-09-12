"""Tests for Easywave neo capability helpers."""

from homeassistant.components.easywave.neo import sensor_learn_capabilities


def test_sensor_learn_capabilities_uses_library_semantics() -> None:
    """Stored capability masks are interpreted via the library codec."""
    capabilities = sensor_learn_capabilities((1 << 4) | (1 << 5))

    assert capabilities.measures_temperature is True
    assert capabilities.measures_humidity is True


def test_sensor_learn_capabilities_without_measurements() -> None:
    """A zero capability mask reports no supported measurements."""
    capabilities = sensor_learn_capabilities(0)

    assert capabilities.measures_temperature is False
    assert capabilities.measures_humidity is False
