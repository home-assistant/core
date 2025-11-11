"""Tests for Rust core optimizations.

These tests ensure that the Rust implementations produce identical results
to the Python implementations and are safe to use in async contexts.
"""

import asyncio
from typing import Any

import pytest

from homeassistant.rust_core import (
    RUST_AVAILABLE,
    _python_fast_attributes_equal,
    _python_split_entity_id,
    _python_valid_domain,
    _python_valid_entity_id,
    fast_attributes_equal,
    split_entity_id,
    valid_domain,
    valid_entity_id,
)


class TestEntityIdValidation:
    """Test entity ID validation correctness."""

    VALID_ENTITY_IDS = [
        "light.living_room",
        "sensor.temperature",
        "binary_sensor.motion_detector",
        "switch.kitchen_light",
        "climate.bedroom",
        "media_player.tv",
        "automation.morning_routine",
        "script.bedtime",
        "cover.garage_door",
        "lock.front_door",
        "zwave.node_2",
        "sensor.temp_1_2_3",
        "a.b",  # Minimum valid
    ]

    INVALID_ENTITY_IDS = [
        "light",  # No object_id
        "light.",  # Empty object_id
        ".living_room",  # Empty domain
        "Light.living",  # Uppercase domain
        "light.Living",  # Uppercase object_id
        "1light.living",  # Domain starts with number
        "light._living",  # Object_id starts with underscore
        "light.living_",  # Object_id ends with underscore
        "",  # Empty
        "light.living.room",  # Multiple periods
        "light-sensor.living",  # Hyphen in domain
        "light.living-room",  # Hyphen in object_id
        "light sensor.living",  # Space in domain
        "light.living room",  # Space in object_id
    ]

    def test_valid_entity_ids(self) -> None:
        """Test that valid entity IDs are recognized."""
        for entity_id in self.VALID_ENTITY_IDS:
            python_result = _python_valid_entity_id(entity_id)
            rust_result = valid_entity_id(entity_id)
            assert python_result == rust_result, f"Mismatch for {entity_id}"
            assert rust_result is True, f"Should be valid: {entity_id}"

    def test_invalid_entity_ids(self) -> None:
        """Test that invalid entity IDs are rejected."""
        for entity_id in self.INVALID_ENTITY_IDS:
            python_result = _python_valid_entity_id(entity_id)
            rust_result = valid_entity_id(entity_id)
            assert python_result == rust_result, f"Mismatch for {entity_id}"
            assert rust_result is False, f"Should be invalid: {entity_id}"

    @pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust extension not available")
    async def test_async_safety(self) -> None:
        """Test that validation is safe to call from async context."""

        async def validate_many():
            tasks = [
                asyncio.to_thread(valid_entity_id, entity_id)
                for entity_id in self.VALID_ENTITY_IDS * 100
            ]
            results = await asyncio.gather(*tasks)
            assert all(results)

        await validate_many()


class TestDomainValidation:
    """Test domain validation correctness."""

    VALID_DOMAINS = [
        "light",
        "sensor",
        "binarysensor",
        "switch",
        "climate",
        "mediaplayer",
        "automation",
        "script",
        "cover",
        "lock",
        "zwave",
        "zwave2mqtt",
        "homeassistant",
        "a",  # Minimum valid
    ]

    INVALID_DOMAINS = [
        "Light",  # Uppercase
        "1light",  # Starts with number
        "light_sensor",  # Underscore
        "light-sensor",  # Hyphen
        "light.sensor",  # Period
        "light sensor",  # Space
        "",  # Empty
        "a" * 65,  # Too long
    ]

    def test_valid_domains(self) -> None:
        """Test that valid domains are recognized."""
        for domain in self.VALID_DOMAINS:
            python_result = _python_valid_domain(domain)
            rust_result = valid_domain(domain)
            assert python_result == rust_result, f"Mismatch for {domain}"
            assert rust_result is True, f"Should be valid: {domain}"

    def test_invalid_domains(self) -> None:
        """Test that invalid domains are rejected."""
        for domain in self.INVALID_DOMAINS:
            python_result = _python_valid_domain(domain)
            rust_result = valid_domain(domain)
            assert python_result == rust_result, f"Mismatch for {domain}"
            assert rust_result is False, f"Should be invalid: {domain}"


class TestEntityIdSplit:
    """Test entity ID splitting correctness."""

    VALID_SPLITS = [
        ("light.living_room", ("light", "living_room")),
        ("sensor.temperature", ("sensor", "temperature")),
        ("binary_sensor.motion", ("binary_sensor", "motion")),
        ("a.b", ("a", "b")),
    ]

    INVALID_SPLITS = [
        "light",  # No period
        "light.",  # Empty object_id
        ".living",  # Empty domain
        "",  # Empty
    ]

    def test_valid_splits(self) -> None:
        """Test that entity IDs are split correctly."""
        for entity_id, expected in self.VALID_SPLITS:
            python_result = _python_split_entity_id(entity_id)
            rust_result = split_entity_id(entity_id)
            assert python_result == rust_result, f"Mismatch for {entity_id}"
            assert rust_result == expected, f"Wrong split for {entity_id}"

    def test_invalid_splits(self) -> None:
        """Test that invalid entity IDs raise ValueError."""
        for entity_id in self.INVALID_SPLITS:
            with pytest.raises(ValueError):
                _python_split_entity_id(entity_id)
            with pytest.raises(ValueError):
                split_entity_id(entity_id)


class TestAttributeComparison:
    """Test attribute dictionary comparison correctness."""

    def test_identical_dicts(self) -> None:
        """Test that identical dicts are equal."""
        dict1 = {"brightness": 255, "color_temp": 370}
        dict2 = {"brightness": 255, "color_temp": 370}

        python_result = _python_fast_attributes_equal(dict1, dict2)
        rust_result = fast_attributes_equal(dict1, dict2)

        assert python_result == rust_result
        assert rust_result is True

    def test_same_reference(self) -> None:
        """Test that same reference is equal."""
        dict1 = {"brightness": 255, "color_temp": 370}

        python_result = _python_fast_attributes_equal(dict1, dict1)
        rust_result = fast_attributes_equal(dict1, dict1)

        assert python_result == rust_result
        assert rust_result is True

    def test_different_values(self) -> None:
        """Test that dicts with different values are not equal."""
        dict1 = {"brightness": 255, "color_temp": 370}
        dict2 = {"brightness": 200, "color_temp": 370}

        python_result = _python_fast_attributes_equal(dict1, dict2)
        rust_result = fast_attributes_equal(dict1, dict2)

        assert python_result == rust_result
        assert rust_result is False

    def test_different_keys(self) -> None:
        """Test that dicts with different keys are not equal."""
        dict1 = {"brightness": 255}
        dict2 = {"color_temp": 370}

        python_result = _python_fast_attributes_equal(dict1, dict2)
        rust_result = fast_attributes_equal(dict1, dict2)

        assert python_result == rust_result
        assert rust_result is False

    def test_different_sizes(self) -> None:
        """Test that dicts with different sizes are not equal."""
        dict1 = {"brightness": 255}
        dict2 = {"brightness": 255, "color_temp": 370}

        python_result = _python_fast_attributes_equal(dict1, dict2)
        rust_result = fast_attributes_equal(dict1, dict2)

        assert python_result == rust_result
        assert rust_result is False

    def test_empty_dicts(self) -> None:
        """Test that empty dicts are equal."""
        dict1: dict[str, Any] = {}
        dict2: dict[str, Any] = {}

        python_result = _python_fast_attributes_equal(dict1, dict2)
        rust_result = fast_attributes_equal(dict1, dict2)

        assert python_result == rust_result
        assert rust_result is True

    def test_nested_values(self) -> None:
        """Test that nested values are compared correctly."""
        dict1 = {"rgb_color": [255, 255, 255], "effect_list": ["none", "colorloop"]}
        dict2 = {"rgb_color": [255, 255, 255], "effect_list": ["none", "colorloop"]}

        python_result = _python_fast_attributes_equal(dict1, dict2)
        rust_result = fast_attributes_equal(dict1, dict2)

        assert python_result == rust_result
        assert rust_result is True

    def test_nested_different(self) -> None:
        """Test that nested differences are detected."""
        dict1 = {"rgb_color": [255, 255, 255]}
        dict2 = {"rgb_color": [255, 255, 254]}

        python_result = _python_fast_attributes_equal(dict1, dict2)
        rust_result = fast_attributes_equal(dict1, dict2)

        assert python_result == rust_result
        assert rust_result is False

    def test_none_values(self) -> None:
        """Test that None values are handled correctly."""
        dict1 = {"brightness": None, "color_temp": 370}
        dict2 = {"brightness": None, "color_temp": 370}

        python_result = _python_fast_attributes_equal(dict1, dict2)
        rust_result = fast_attributes_equal(dict1, dict2)

        assert python_result == rust_result
        assert rust_result is True

    def test_mixed_types(self) -> None:
        """Test that mixed types are handled correctly."""
        dict1 = {
            "brightness": 255,
            "color_temp": 370.5,
            "name": "test",
            "enabled": True,
            "metadata": None,
            "rgb": [255, 255, 255],
        }
        dict2 = {
            "brightness": 255,
            "color_temp": 370.5,
            "name": "test",
            "enabled": True,
            "metadata": None,
            "rgb": [255, 255, 255],
        }

        python_result = _python_fast_attributes_equal(dict1, dict2)
        rust_result = fast_attributes_equal(dict1, dict2)

        assert python_result == rust_result
        assert rust_result is True

    @pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust extension not available")
    async def test_async_safety(self) -> None:
        """Test that comparison is safe to call from async context."""
        dict1 = {"brightness": 255, "color_temp": 370}
        dict2 = {"brightness": 255, "color_temp": 370}

        async def compare_many():
            tasks = [
                asyncio.to_thread(fast_attributes_equal, dict1, dict2)
                for _ in range(1000)
            ]
            results = await asyncio.gather(*tasks)
            assert all(results)

        await compare_many()


class TestRealWorldAttributes:
    """Test with realistic Home Assistant attribute dictionaries."""

    def test_light_attributes(self) -> None:
        """Test with typical light entity attributes."""
        dict1 = {
            "brightness": 255,
            "color_temp": 370,
            "rgb_color": [255, 255, 255],
            "xy_color": [0.323, 0.329],
            "hs_color": [0.0, 0.0],
            "effect": "none",
            "effect_list": ["none", "colorloop", "random"],
            "friendly_name": "Living Room Light",
            "supported_features": 63,
            "min_mireds": 153,
            "max_mireds": 500,
        }
        dict2 = dict1.copy()

        python_result = _python_fast_attributes_equal(dict1, dict2)
        rust_result = fast_attributes_equal(dict1, dict2)

        assert python_result == rust_result
        assert rust_result is True

    def test_sensor_attributes(self) -> None:
        """Test with typical sensor entity attributes."""
        dict1 = {
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
            "friendly_name": "Living Room Temperature",
        }
        dict2 = dict1.copy()

        python_result = _python_fast_attributes_equal(dict1, dict2)
        rust_result = fast_attributes_equal(dict1, dict2)

        assert python_result == rust_result
        assert rust_result is True
