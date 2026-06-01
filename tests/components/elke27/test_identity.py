"""Tests for Elke27 identity helpers."""

from homeassistant.components.elke27 import identity as identity_module


def test_derive_client_id() -> None:
    """Verify client IDs are derived from Home Assistant entry IDs."""
    assert identity_module.derive_client_id("01ABC-def_23") == "01abcdef23"
    assert identity_module.derive_client_id("01ABC-déf_23") == "01abcdf23"


def test_build_client_identity() -> None:
    """Verify client identity payload."""
    identity = identity_module.build_client_identity("entryclientid")
    assert identity == {
        "mn": str(identity_module.MANUFACTURER_NUMBER),
        "sn": "entryclientid",
    }
