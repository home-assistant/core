"""Tests for neo sensor type labels in the config flow."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.easywave.config_flow_learning import (
    EasywaveDeviceFlowMixin,
)
from homeassistant.components.easywave.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import LOCALE_EN, async_get_translations


class _SensorListHelper(EasywaveDeviceFlowMixin):
    """Minimal mixin wrapper for translation helper tests."""


@pytest.mark.parametrize(
    ("learned_device", "expected"),
    [
        pytest.param(
            {
                "measures_temperature": True,
                "measures_humidity": True,
            },
            "• Temperature\n• Humidity",
            id="temperature_and_humidity",
        ),
        pytest.param(
            {
                "measures_temperature": True,
                "measures_humidity": False,
            },
            "• Temperature",
            id="temperature_only",
        ),
        pytest.param(
            {
                "measures_temperature": False,
                "measures_humidity": False,
            },
            "• Unknown",
            id="unknown",
        ),
    ],
)
async def test_async_format_neo_sensor_list(
    hass: HomeAssistant,
    learned_device: dict[str, Any],
    expected: str,
) -> None:
    """Supported neo sensor capabilities are listed with entity translations."""
    helper = _SensorListHelper()
    helper.hass = hass

    assert await helper._async_format_neo_sensor_list(learned_device) == expected


async def test_config_flow_translation_keys_exist(hass: HomeAssistant) -> None:
    """Verify strings used by the config flow resolve via the translation loader."""
    entity_translations = await async_get_translations(
        hass, LOCALE_EN, "entity", integrations=[DOMAIN]
    )
    selector_translations = await async_get_translations(
        hass, LOCALE_EN, "selector", integrations=[DOMAIN]
    )
    config_translations = await async_get_translations(
        hass, LOCALE_EN, "config", integrations=[DOMAIN], config_flow=True
    )

    entity_prefix = f"component.{DOMAIN}.entity.sensor."
    assert (
        entity_translations[f"{entity_prefix}neo_sensor_temperature.name"]
        == "Temperature"
    )
    assert entity_translations[f"{entity_prefix}neo_sensor_humidity.name"] == "Humidity"
    assert (
        selector_translations[
            f"component.{DOMAIN}.selector.sensor_type.options.unknown"
        ]
        == "Unknown"
    )
    assert (
        "{sensor_list}"
        in config_translations[
            f"component.{DOMAIN}.config.step.sensor_confirm.description"
        ]
    )
    assert (
        config_translations[
            f"component.{DOMAIN}.config.step.transmitter_learn_intro.title"
        ]
        == "Learn Transmitter"
    )


async def test_config_flow_sensor_list_uses_language_fallback(
    hass: HomeAssistant,
) -> None:
    """German falls back to English until Lokalise provides component translations."""
    helper = _SensorListHelper()
    helper.hass = hass

    with patch.object(hass.config, "language", "de"):
        sensor_list = await helper._async_format_neo_sensor_list(
            {"measures_temperature": True, "measures_humidity": True}
        )
    assert sensor_list == "• Temperature\n• Humidity"
