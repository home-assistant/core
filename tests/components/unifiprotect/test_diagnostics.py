"""Test UniFi Protect diagnostics."""

import re
from typing import Any

from syrupy.assertion import SnapshotAssertion
from uiprotect.data import Light

from homeassistant.core import HomeAssistant

from .utils import MockUFPFixture, init_entry

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

# Pattern for hex IDs (24 char hex strings like device/user IDs)
HEX_ID_PATTERN = re.compile(r"^[a-f0-9]{24}$")
# Pattern for MAC addresses (12 hex chars)
MAC_PATTERN = re.compile(r"^[A-F0-9]{12}$")
# Pattern for IPv4 addresses (anonymized by library)
IPV4_PATTERN = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
# Pattern for UUIDs (anonymized by library)
UUID_PATTERN = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
)
# Pattern for anonymized names (capitalized words with random letters)
ANON_NAME_PATTERN = re.compile(r"^[A-Z][a-z]+( [A-Z][a-z]+)*$")
# Pattern for anonymized emails
EMAIL_PATTERN = re.compile(r"^[A-Za-z]+@example\.com$")
# Pattern for permission strings with embedded IDs
PERMISSION_ID_PATTERN = re.compile(r"^(.+:\*:)[a-f0-9]{24}$")
# Keys that should be redacted for security
REDACT_KEYS = {"accessKey"}
# Keys that contain anonymized names (need normalization) - pattern-matched
NAME_KEYS = {"name", "firstName", "lastName"}
# Keys that always need normalization (not pattern-matched)
ALWAYS_REDACT_KEYS = {"localUsername"}


def _normalize_diagnostics(data: Any, parent_key: str | None = None) -> Any:
    """Normalize diagnostics data for deterministic snapshots.

    Removes repr fields (contain memory addresses), redacts sensitive keys,
    and normalizes hex IDs, MAC addresses, IP addresses, UUIDs, emails, and
    anonymized names that may be randomly generated.
    """
    if isinstance(data, dict):
        return {
            k: _normalize_diagnostics(v, k)
            for k, v in data.items()
            if k != "repr"  # Remove repr fields with memory addresses
        }
    if isinstance(data, list):
        return [_normalize_diagnostics(item) for item in data]
    if isinstance(data, str):
        # Redact sensitive keys
        if parent_key in REDACT_KEYS:
            return "**REDACTED**"
        # Always redact certain keys regardless of pattern
        if parent_key in ALWAYS_REDACT_KEYS:
            return "**REDACTED_NAME**"
        # Normalize anonymized names (pattern-matched)
        if parent_key in NAME_KEYS and ANON_NAME_PATTERN.match(data):
            return "**REDACTED_NAME**"
        if HEX_ID_PATTERN.match(data):
            return "**REDACTED_ID**"
        if MAC_PATTERN.match(data):
            return "**REDACTED_MAC**"
        if IPV4_PATTERN.match(data):
            return "**REDACTED_IP**"
        if UUID_PATTERN.match(data):
            return "**REDACTED_UUID**"
        if EMAIL_PATTERN.match(data):
            return "**REDACTED**@example.com"
        # Normalize permission strings with embedded IDs
        if match := PERMISSION_ID_PATTERN.match(data):
            return f"{match.group(1)}**REDACTED_ID**"
    return data


async def test_diagnostics(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    light: Light,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    await init_entry(hass, ufp, [light])

    diag = await get_diagnostics_for_config_entry(hass, hass_client, ufp.entry)

    # Validate that anonymization is working - original values should not appear
    bootstrap = diag["bootstrap"]
    nvr = ufp.api.bootstrap.nvr
    assert bootstrap["nvr"]["id"] != nvr.id
    assert bootstrap["nvr"]["mac"] != nvr.mac
    assert bootstrap["nvr"]["host"] != str(nvr.host)
    assert bootstrap["lights"][0]["id"] != light.id
    assert bootstrap["lights"][0]["mac"] != light.mac
    assert bootstrap["lights"][0]["host"] != str(light.host)

    # Normalize data to remove non-deterministic values (memory addresses, random IDs)
    diag_normalized = _normalize_diagnostics(diag)

    assert diag_normalized == snapshot
