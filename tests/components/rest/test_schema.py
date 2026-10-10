"""Tests for RESTful schema.py."""

from probatio import Invalid
import pytest

from homeassistant.components.rest.schema import KeyedTemplateSelector
from homeassistant.core import HomeAssistant


def test_keyed_template_selector_duplicate_keys(
    hass: HomeAssistant,
) -> None:
    """Test if the KeyedTemplateSelector validation raises for duplicate keys."""

    kts = KeyedTemplateSelector("test_selector")

    with pytest.raises(Invalid) as ex:
        kts(
            [
                {"key": "test_key", "value": "test_value"},
                {"key": "test_key", "value": "test_value1"},
            ]
        )

    assert "Duplicate keys" in str(ex)
