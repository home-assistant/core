"""Performance benchmarks for Rust core optimizations.

These benchmarks measure the performance improvements of Rust implementations
over Python implementations for critical hot paths in Home Assistant core.
"""

import pytest
from pytest_codspeed import BenchmarkFixture

# Import both Rust and Python implementations
from homeassistant.rust_core import (
    RUST_AVAILABLE,
    fast_attributes_equal,
    split_entity_id,
    valid_domain,
    valid_entity_id,
)
from homeassistant.rust_core import (
    _python_fast_attributes_equal,
    _python_split_entity_id,
    _python_valid_domain,
    _python_valid_entity_id,
)

# Test data
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
]

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
]

INVALID_DOMAINS = [
    "Light",  # Uppercase
    "1light",  # Starts with number
    "light_sensor",  # Underscore
    "light-sensor",  # Hyphen
    "",  # Empty
]

# Attribute test data (simulating real entity attributes)
SMALL_ATTRIBUTES = {
    "brightness": 255,
    "color_temp": 370,
}

MEDIUM_ATTRIBUTES = {
    "brightness": 255,
    "color_temp": 370,
    "rgb_color": [255, 255, 255],
    "effect": "none",
    "friendly_name": "Living Room Light",
    "supported_features": 63,
}

LARGE_ATTRIBUTES = {
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
    "icon": "mdi:lightbulb",
    "entity_id": "light.living_room",
    "last_changed": "2024-01-01T00:00:00",
    "last_updated": "2024-01-01T00:00:00",
}

DIFFERENT_LARGE_ATTRIBUTES = {
    "brightness": 200,  # Different value
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
    "icon": "mdi:lightbulb",
    "entity_id": "light.living_room",
    "last_changed": "2024-01-01T00:00:00",
    "last_updated": "2024-01-01T00:00:00",
}


class TestEntityIdValidationPerformance:
    """Benchmarks for entity ID validation."""

    @pytest.mark.benchmark
    def test_valid_entity_id_rust_valid(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark Rust implementation with valid entity IDs."""
        if not RUST_AVAILABLE:
            pytest.skip("Rust extension not available")

        @benchmark
        def run():
            for entity_id in VALID_ENTITY_IDS:
                valid_entity_id(entity_id)

    @pytest.mark.benchmark
    def test_valid_entity_id_python_valid(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark Python implementation with valid entity IDs."""

        @benchmark
        def run():
            for entity_id in VALID_ENTITY_IDS:
                _python_valid_entity_id(entity_id)

    @pytest.mark.benchmark
    def test_valid_entity_id_rust_invalid(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark Rust implementation with invalid entity IDs."""
        if not RUST_AVAILABLE:
            pytest.skip("Rust extension not available")

        @benchmark
        def run():
            for entity_id in INVALID_ENTITY_IDS:
                valid_entity_id(entity_id)

    @pytest.mark.benchmark
    def test_valid_entity_id_python_invalid(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark Python implementation with invalid entity IDs."""

        @benchmark
        def run():
            for entity_id in INVALID_ENTITY_IDS:
                _python_valid_entity_id(entity_id)


class TestDomainValidationPerformance:
    """Benchmarks for domain validation."""

    @pytest.mark.benchmark
    def test_valid_domain_rust_valid(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark Rust implementation with valid domains."""
        if not RUST_AVAILABLE:
            pytest.skip("Rust extension not available")

        @benchmark
        def run():
            for domain in VALID_DOMAINS:
                valid_domain(domain)

    @pytest.mark.benchmark
    def test_valid_domain_python_valid(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark Python implementation with valid domains."""

        @benchmark
        def run():
            for domain in VALID_DOMAINS:
                _python_valid_domain(domain)


class TestEntityIdSplitPerformance:
    """Benchmarks for entity ID splitting."""

    @pytest.mark.benchmark
    def test_split_entity_id_rust(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark Rust implementation of entity ID splitting."""
        if not RUST_AVAILABLE:
            pytest.skip("Rust extension not available")

        @benchmark
        def run():
            for entity_id in VALID_ENTITY_IDS:
                split_entity_id(entity_id)

    @pytest.mark.benchmark
    def test_split_entity_id_python(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark Python implementation of entity ID splitting."""

        @benchmark
        def run():
            for entity_id in VALID_ENTITY_IDS:
                _python_split_entity_id(entity_id)


class TestAttributeComparisonPerformance:
    """Benchmarks for attribute dictionary comparison."""

    @pytest.mark.benchmark
    def test_attributes_equal_rust_small_identical(
        self, benchmark: BenchmarkFixture
    ) -> None:
        """Benchmark Rust comparison of small identical dicts."""
        if not RUST_AVAILABLE:
            pytest.skip("Rust extension not available")

        dict1 = SMALL_ATTRIBUTES
        dict2 = SMALL_ATTRIBUTES.copy()

        @benchmark
        def run():
            fast_attributes_equal(dict1, dict2)

    @pytest.mark.benchmark
    def test_attributes_equal_python_small_identical(
        self, benchmark: BenchmarkFixture
    ) -> None:
        """Benchmark Python comparison of small identical dicts."""
        dict1 = SMALL_ATTRIBUTES
        dict2 = SMALL_ATTRIBUTES.copy()

        @benchmark
        def run():
            _python_fast_attributes_equal(dict1, dict2)

    @pytest.mark.benchmark
    def test_attributes_equal_rust_medium_identical(
        self, benchmark: BenchmarkFixture
    ) -> None:
        """Benchmark Rust comparison of medium identical dicts."""
        if not RUST_AVAILABLE:
            pytest.skip("Rust extension not available")

        dict1 = MEDIUM_ATTRIBUTES
        dict2 = MEDIUM_ATTRIBUTES.copy()

        @benchmark
        def run():
            fast_attributes_equal(dict1, dict2)

    @pytest.mark.benchmark
    def test_attributes_equal_python_medium_identical(
        self, benchmark: BenchmarkFixture
    ) -> None:
        """Benchmark Python comparison of medium identical dicts."""
        dict1 = MEDIUM_ATTRIBUTES
        dict2 = MEDIUM_ATTRIBUTES.copy()

        @benchmark
        def run():
            _python_fast_attributes_equal(dict1, dict2)

    @pytest.mark.benchmark
    def test_attributes_equal_rust_large_identical(
        self, benchmark: BenchmarkFixture
    ) -> None:
        """Benchmark Rust comparison of large identical dicts."""
        if not RUST_AVAILABLE:
            pytest.skip("Rust extension not available")

        dict1 = LARGE_ATTRIBUTES
        dict2 = LARGE_ATTRIBUTES.copy()

        @benchmark
        def run():
            fast_attributes_equal(dict1, dict2)

    @pytest.mark.benchmark
    def test_attributes_equal_python_large_identical(
        self, benchmark: BenchmarkFixture
    ) -> None:
        """Benchmark Python comparison of large identical dicts."""
        dict1 = LARGE_ATTRIBUTES
        dict2 = LARGE_ATTRIBUTES.copy()

        @benchmark
        def run():
            _python_fast_attributes_equal(dict1, dict2)

    @pytest.mark.benchmark
    def test_attributes_equal_rust_large_different(
        self, benchmark: BenchmarkFixture
    ) -> None:
        """Benchmark Rust comparison of large different dicts."""
        if not RUST_AVAILABLE:
            pytest.skip("Rust extension not available")

        dict1 = LARGE_ATTRIBUTES
        dict2 = DIFFERENT_LARGE_ATTRIBUTES

        @benchmark
        def run():
            fast_attributes_equal(dict1, dict2)

    @pytest.mark.benchmark
    def test_attributes_equal_python_large_different(
        self, benchmark: BenchmarkFixture
    ) -> None:
        """Benchmark Python comparison of large different dicts."""
        dict1 = LARGE_ATTRIBUTES
        dict2 = DIFFERENT_LARGE_ATTRIBUTES

        @benchmark
        def run():
            _python_fast_attributes_equal(dict1, dict2)

    @pytest.mark.benchmark
    def test_attributes_equal_rust_same_reference(
        self, benchmark: BenchmarkFixture
    ) -> None:
        """Benchmark Rust comparison of same reference (fastest path)."""
        if not RUST_AVAILABLE:
            pytest.skip("Rust extension not available")

        dict1 = LARGE_ATTRIBUTES

        @benchmark
        def run():
            fast_attributes_equal(dict1, dict1)

    @pytest.mark.benchmark
    def test_attributes_equal_python_same_reference(
        self, benchmark: BenchmarkFixture
    ) -> None:
        """Benchmark Python comparison of same reference."""
        dict1 = LARGE_ATTRIBUTES

        @benchmark
        def run():
            _python_fast_attributes_equal(dict1, dict1)


class TestRealWorldSimulation:
    """Benchmarks simulating real-world usage patterns."""

    @pytest.mark.benchmark
    def test_state_update_simulation_rust(self, benchmark: BenchmarkFixture) -> None:
        """Simulate a typical state update with Rust optimizations."""
        if not RUST_AVAILABLE:
            pytest.skip("Rust extension not available")

        @benchmark
        def run():
            # Typical state update: validate entity ID, compare attributes
            for entity_id in VALID_ENTITY_IDS:
                if valid_entity_id(entity_id):
                    domain, _ = split_entity_id(entity_id)
                    if valid_domain(domain):
                        fast_attributes_equal(MEDIUM_ATTRIBUTES, MEDIUM_ATTRIBUTES)

    @pytest.mark.benchmark
    def test_state_update_simulation_python(self, benchmark: BenchmarkFixture) -> None:
        """Simulate a typical state update with Python implementations."""

        @benchmark
        def run():
            # Typical state update: validate entity ID, compare attributes
            for entity_id in VALID_ENTITY_IDS:
                if _python_valid_entity_id(entity_id):
                    domain, _ = _python_split_entity_id(entity_id)
                    if _python_valid_domain(domain):
                        _python_fast_attributes_equal(
                            MEDIUM_ATTRIBUTES, MEDIUM_ATTRIBUTES
                        )
