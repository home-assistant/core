"""The tests for the climate component."""
from __future__ import annotations

from enum import Enum
from types import ModuleType
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from homeassistant.components import climate
from homeassistant.components.climate import (
    SET_TEMPERATURE_SCHEMA,
    ClimateEntity,
    HVACMode,
)
from homeassistant.core import HomeAssistant

from tests.common import (
    async_mock_service,
    import_and_test_deprecated_constant,
    import_and_test_deprecated_constant_enum,
)


async def test_set_temp_schema_no_req(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with missing required data."""
    domain = "climate"
    service = "test_set_temperature"
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {"hvac_mode": "off", "entity_id": ["climate.test_id"]}
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_set_temp_schema(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with ok required data."""
    domain = "climate"
    service = "test_set_temperature"
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {"temperature": 20.0, "hvac_mode": "heat", "entity_id": ["climate.test_id"]}
    await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[-1].data == data


class MockClimateEntity(ClimateEntity):
    """Mock Climate device to use in tests."""

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVACMode.*.
        """
        return HVACMode.HEAT

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVACMode.OFF, HVACMode.HEAT]

    def turn_on(self) -> None:
        """Turn on."""

    def turn_off(self) -> None:
        """Turn off."""


async def test_sync_turn_on(hass: HomeAssistant) -> None:
    """Test if async turn_on calls sync turn_on."""
    climate = MockClimateEntity()
    climate.hass = hass

    climate.turn_on = MagicMock()
    await climate.async_turn_on()

    assert climate.turn_on.called


async def test_sync_turn_off(hass: HomeAssistant) -> None:
    """Test if async turn_off calls sync turn_off."""
    climate = MockClimateEntity()
    climate.hass = hass

    climate.turn_off = MagicMock()
    await climate.async_turn_off()

    assert climate.turn_off.called


def _create_tuples(enum: Enum, constant_prefix: str) -> list[tuple[Enum, str]]:
    result = []
    for enum in enum:
        result.append((enum, constant_prefix))
    return result


@pytest.mark.parametrize(
    ("enum", "constant_prefix"),
    _create_tuples(climate.ClimateEntityFeature, "SUPPORT_")
    + _create_tuples(climate.HVACMode, "HVAC_MODE_"),
)
@pytest.mark.parametrize(
    "module",
    [climate, climate.const],
)
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: Enum,
    constant_prefix: str,
    module: ModuleType,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(
        caplog, module, enum, constant_prefix, "2025.1"
    )


@pytest.mark.parametrize(
    ("enum", "constant_postfix"),
    [
        (climate.HVACAction.OFF, "OFF"),
        (climate.HVACAction.HEATING, "HEAT"),
        (climate.HVACAction.COOLING, "COOL"),
        (climate.HVACAction.DRYING, "DRY"),
        (climate.HVACAction.IDLE, "IDLE"),
        (climate.HVACAction.FAN, "FAN"),
    ],
)
def test_deprecated_current_constants(
    caplog: pytest.LogCaptureFixture,
    enum: climate.HVACAction,
    constant_postfix: str,
) -> None:
    """Test deprecated current constants."""
    import_and_test_deprecated_constant(
        caplog,
        climate.const,
        "CURRENT_HVAC_" + constant_postfix,
        f"{enum.__class__.__name__}.{enum.name}",
        enum,
        "2025.1",
    )
