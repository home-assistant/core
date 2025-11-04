"""Simple test script for Rust core optimizations."""

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


def test_entity_id_validation():
    """Test entity ID validation."""
    print("Testing entity ID validation...")

    valid_ids = [
        "light.living_room",
        "sensor.temperature",
        "binary_sensor.motion",
    ]

    invalid_ids = [
        "light",
        "light.",
        ".living",
        "Light.test",
    ]

    for entity_id in valid_ids:
        py_result = _python_valid_entity_id(entity_id)
        rust_result = valid_entity_id(entity_id)
        assert py_result == rust_result, f"Mismatch for {entity_id}"
        assert rust_result is True, f"Should be valid: {entity_id}"
        print(f"  ✓ {entity_id}: valid")

    for entity_id in invalid_ids:
        py_result = _python_valid_entity_id(entity_id)
        rust_result = valid_entity_id(entity_id)
        assert py_result == rust_result, f"Mismatch for {entity_id}"
        assert rust_result is False, f"Should be invalid: {entity_id}"
        print(f"  ✓ {entity_id}: invalid")

    print("✅ Entity ID validation tests passed!\n")


def test_domain_validation():
    """Test domain validation."""
    print("Testing domain validation...")

    valid_domains = ["light", "sensor", "switch", "zwave2mqtt", "1light"]
    invalid_domains = ["Light", "light__sensor", "_light"]

    for domain in valid_domains:
        py_result = _python_valid_domain(domain)
        rust_result = valid_domain(domain)
        assert py_result == rust_result, f"Mismatch for {domain}"
        assert rust_result is True, f"Should be valid: {domain}"
        print(f"  ✓ {domain}: valid")

    for domain in invalid_domains:
        py_result = _python_valid_domain(domain)
        rust_result = valid_domain(domain)
        assert py_result == rust_result, f"Mismatch for {domain}"
        assert rust_result is False, f"Should be invalid: {domain}"
        print(f"  ✓ {domain}: invalid")

    print("✅ Domain validation tests passed!\n")


def test_entity_id_split():
    """Test entity ID splitting."""
    print("Testing entity ID splitting...")

    test_cases = [
        ("light.living_room", ("light", "living_room")),
        ("sensor.temp", ("sensor", "temp")),
    ]

    for entity_id, expected in test_cases:
        py_result = _python_split_entity_id(entity_id)
        rust_result = split_entity_id(entity_id)
        assert py_result == rust_result, f"Mismatch for {entity_id}"
        assert rust_result == expected, f"Wrong split for {entity_id}"
        print(f"  ✓ {entity_id} -> {expected}")

    print("✅ Entity ID split tests passed!\n")


def test_attribute_comparison():
    """Test attribute comparison."""
    print("Testing attribute comparison...")

    dict1 = {"brightness": 255, "color_temp": 370}
    dict2 = {"brightness": 255, "color_temp": 370}
    dict3 = {"brightness": 200, "color_temp": 370}

    # Test equal dicts
    py_result = _python_fast_attributes_equal(dict1, dict2)
    rust_result = fast_attributes_equal(dict1, dict2)
    assert py_result == rust_result
    assert rust_result is True
    print("  ✓ Equal dicts: correct")

    # Test different dicts
    py_result = _python_fast_attributes_equal(dict1, dict3)
    rust_result = fast_attributes_equal(dict1, dict3)
    assert py_result == rust_result
    assert rust_result is False
    print("  ✓ Different dicts: correct")

    # Test same reference
    py_result = _python_fast_attributes_equal(dict1, dict1)
    rust_result = fast_attributes_equal(dict1, dict1)
    assert py_result == rust_result
    assert rust_result is True
    print("  ✓ Same reference: correct")

    print("✅ Attribute comparison tests passed!\n")


if __name__ == "__main__":
    print(f"Rust available: {RUST_AVAILABLE}\n")
    print("Running tests with {'Rust' if RUST_AVAILABLE else 'Python fallback'} implementation...\n")
    print("=" * 60)

    test_entity_id_validation()
    test_domain_validation()
    test_entity_id_split()
    test_attribute_comparison()

    print("=" * 60)
    print("✅ All tests passed!")
    print("\nThe Rust core module is working correctly with Python fallback.")
