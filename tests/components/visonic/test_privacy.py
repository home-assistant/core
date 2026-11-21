"""Protect panel identifications in Core log output."""

import logging
from unittest.mock import patch

import pytest

from homeassistant.components.visonic.cloud import VisonicCloudConnection
from homeassistant.components.visonic.const import CONF_PANEL_SERIAL
from homeassistant.components.visonic.direct import VisonicDirectConnection
from homeassistant.components.visonic.identity import redact_panel_identification
from homeassistant.components.visonic.visonic_types import DeviceType
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant

from .helpers import SetupIntegration, create_mock_config_entry


@pytest.mark.parametrize(
    ("value", "identification", "expected"),
    [
        ("Panel ABCDEF", "ABCDEF", "Panel **REDACTED**"),
        ("prefix-abcdef-suffix", "ABCDEF", "prefix-**REDACTED**-suffix"),
        ("ABCDEF / ABCDEF", "ABCDEF", "**REDACTED** / **REDACTED**"),
        ("Panel", "", "Panel"),
        ("Panel", None, "Panel"),
    ],
)
def test_identification_redaction(
    value: str, identification: str | None, expected: str
) -> None:
    """Redact embedded and repeated identification without case sensitivity."""
    assert redact_panel_identification(value, identification) == expected


@pytest.mark.usefixtures("mock_forward_entry_setups", "mock_async_zeroconf")
@pytest.mark.parametrize("device_type", list(DeviceType))
async def test_stored_title_and_setup_error_are_private(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_type: DeviceType,
) -> None:
    """Existing identifying titles and transport errors cannot leak on retry."""
    entry = create_mock_config_entry(
        data={CONF_TYPE: device_type, CONF_PANEL_SERIAL: "ABCDEF"}
    )
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, title="Panel 1 (Identifier abcdef, PowerMaster 30)"
    )
    error = OSError("Transport failure for ABCDEF")
    with (
        caplog.at_level(logging.DEBUG),
        patch.object(VisonicDirectConnection, "async_panel_connect", side_effect=error),
        patch.object(VisonicCloudConnection, "async_panel_connect", side_effect=error),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert "abcdef" not in entry.title.lower()
    assert entry.data[CONF_PANEL_SERIAL] == "ABCDEF"
    assert "abcdef" not in caplog.text.lower()
    assert "Retrying in" in caplog.text


@pytest.mark.parametrize("device_type", list(DeviceType))
async def test_update_exception_does_not_expose_identification(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    caplog: pytest.LogCaptureFixture,
    device_type: DeviceType,
) -> None:
    """Unknown backend update exceptions are safe for polling and push logs."""
    _, entry = await setup_integration(
        data={CONF_TYPE: device_type, CONF_PANEL_SERIAL: "ABCDEF"}
    )
    coordinator = entry.runtime_data.coordinator
    error = RuntimeError("Malformed response from ABCDEF")
    with (
        patch.object(
            coordinator.connection, "create_state_snapshot", side_effect=error
        ),
        caplog.at_level(logging.DEBUG),
    ):
        coordinator.state_changed_callback(0)
        await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert "RuntimeError" in caplog.text
    assert "abcdef" not in caplog.text.lower()
