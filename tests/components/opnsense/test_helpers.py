"""Unit tests for helper functions in the OPNsense integration."""

from homeassistant.components.opnsense import helpers as helpers_module


def test_dict_get_numeric_segments_and_missing_host() -> None:
    """Helper lookups should handle numeric path segments and hostname-less URLs."""
    data = {0: "first"}
    assert helpers_module.dict_get(data, "0") == "first"
    assert helpers_module.is_private_ip("https://192.168.1.1") is True
    assert helpers_module.is_private_ip("https:///missing-host") is False
