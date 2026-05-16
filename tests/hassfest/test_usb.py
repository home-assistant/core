"""Tests for the hassfest USB manifest schema."""

import pytest
import voluptuous as vol

from script.hassfest.manifest import USB_LEGACY_DOMAINS, manifest_schema


def _manifest_with_usb(domain: str, usb: list[dict]) -> dict:
    return {
        "domain": domain,
        "name": domain,
        "documentation": f"https://www.home-assistant.io/integrations/{domain}",
        "codeowners": ["@home-assistant"],
        "iot_class": "local_push",
        "usb": usb,
    }


def test_entry_with_all_required_fields_passes() -> None:
    """A USB entry with vid, pid, manufacturer and description is accepted."""
    manifest_schema(
        _manifest_with_usb(
            "test",
            [
                {
                    "vid": "10C4",
                    "pid": "EA60",
                    "manufacturer": "silicon labs",
                    "description": "*cc2652*",
                }
            ],
        )
    )


@pytest.mark.parametrize("missing", ["vid", "pid", "manufacturer", "description"])
def test_entry_missing_required_field_rejected(missing: str) -> None:
    """An entry missing any required field is rejected for non-legacy domains."""
    entry = {
        "vid": "10C4",
        "pid": "EA60",
        "manufacturer": "silicon labs",
        "description": "*cc2652*",
    }
    del entry[missing]

    with pytest.raises(vol.Invalid):
        manifest_schema(_manifest_with_usb("test", [entry]))


def test_legacy_domain_allows_vid_only_entry() -> None:
    """Legacy domains keep the loose schema (vid required, rest optional)."""
    legacy_domain = next(iter(USB_LEGACY_DOMAINS))
    manifest_schema(_manifest_with_usb(legacy_domain, [{"vid": "10BF"}]))
