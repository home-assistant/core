"""Test the Bosch SHC diagnostics."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.components.bosch_shc.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_DATA = {
    "host": "192.168.1.10",
    "ssl_certificate": "/config/bosch_shc/abc/bosch_shc-cert.pem",
    "ssl_key": "/config/bosch_shc/abc/bosch_shc-key.pem",
    "token": "0123456789abcdef:hostname-part",
    "hostname": "hostname-part",
}


def _make_device(device_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=device_id,
        root_device_id="64-da-a0-00-00-00",
        device_model="SWD",
        manufacturer="BOSCH",
        name="Front door",
        room_id="hz_1",
        serial="123456789",
        device_services=[SimpleNamespace(id="ShutterContact", state={"value": "OPEN"})],
    )


async def _get_diagnostics(hass: HomeAssistant) -> dict:
    entry = MockConfigEntry(domain="bosch_shc", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock(
        information=SimpleNamespace(
            version="1.2.3",
            updateState=SimpleNamespace(name="NO_UPDATE_AVAILABLE"),
            macAddress="64-da-a0-00-00-00",
            shcIpAddress="192.168.1.10",
        ),
        devices=[
            _make_device("hdm:ZigBee:5c0272fffe462481"),
            _make_device("swd-1"),
        ],
    )
    return await async_get_config_entry_diagnostics(hass, entry)


async def test_diagnostics_redacts_credentials_and_identifiers(
    hass: HomeAssistant,
) -> None:
    """Credentials and network identifiers must never appear unredacted."""
    diag = await _get_diagnostics(hass)

    entry_data = diag["entry_data"]
    assert entry_data["host"] == REDACTED
    assert entry_data["ssl_certificate"] == REDACTED
    assert entry_data["ssl_key"] == REDACTED
    assert entry_data["token"] == REDACTED
    assert entry_data["hostname"] == REDACTED

    shc = diag["shc"]
    assert shc["macAddress"] == REDACTED
    assert shc["shcIpAddress"] == REDACTED
    assert shc["version"] == "1.2.3"
    assert shc["update_state"] == "NO_UPDATE_AVAILABLE"

    for device in diag["devices"]:
        assert device["device_id"] == REDACTED
        assert device["root_device_id"] == REDACTED
        assert device["serial"] == REDACTED
        # names are not secret and must survive redaction
        assert device["name"] == "Front door"
        # raw service state is the whole point of this diagnostics dump --
        # must survive intact, not just the device metadata around it
        assert device["services"] == [
            {"id": "ShutterContact", "state": {"value": "OPEN"}}
        ]


async def test_diagnostics_update_state_string_fallback(hass: HomeAssistant) -> None:
    """Support the async session's update_state string, not just updateState."""
    entry = MockConfigEntry(domain="bosch_shc", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock(
        information=SimpleNamespace(
            version="1.2.3",
            update_state="NO_UPDATE_AVAILABLE",
            macAddress="64-da-a0-00-00-00",
            shcIpAddress="192.168.1.10",
        ),
        devices=[],
    )
    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["shc"]["update_state"] == "NO_UPDATE_AVAILABLE"
