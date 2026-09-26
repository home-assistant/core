"""Tests for the Cert Expiry diagnostics."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cert_expiry.const import DOMAIN
from homeassistant.components.cert_expiry.errors import HandshakeFailed
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant

from .const import HOST, PORT
from .helpers import certificate_expiring, future_timestamp, static_datetime


@pytest.mark.freeze_time(static_datetime())
@pytest.mark.usefixtures("cert_verified")
async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    # Create fake config entry: simulate "host = example.com, port = 443".
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        entry_id="test-entry",
        title=HOST,
        unique_id=f"{HOST}:{PORT}",
    )

    timestamp = future_timestamp(100)

    # patch network call and setup integration.
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(timestamp),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert (
            await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
        )


@pytest.mark.freeze_time(static_datetime())
async def test_config_entry_retries_when_handshake_fails(
    hass: HomeAssistant,
) -> None:
    """Test the config entry retries setup when the TLS handshake itself fails.

    No certificate is ever obtained, so first refresh fails and setup is retried;
    there is no loaded entry to produce diagnostics for.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        entry_id="test-entry-error",
        title=HOST,
        unique_id=f"{HOST}:{PORT}",
    )

    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        side_effect=HandshakeFailed(HOST, PORT, "handshake failed"),
    ):
        entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.freeze_time(static_datetime())
async def test_config_entry_diagnostics_with_cert_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a verify_cert() error, which embeds the hostname, is redacted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        entry_id="test-entry-cert-error",
        title=HOST,
        unique_id=f"{HOST}:{PORT}",
    )

    timestamp = future_timestamp(100)

    with (
        patch(
            "homeassistant.components.cert_expiry.coordinator.async_get_cert",
            return_value=certificate_expiring(timestamp),
        ),
        patch(
            "homeassistant.components.cert_expiry.coordinator.HandshakePolicyVerifier.verify_cert",
            return_value=f"hostname mismatch, certificate is not valid for {HOST}",
        ),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
        assert diagnostics == snapshot
        assert diagnostics["coordinator"]["data"]["cert_error"] == "**REDACTED**"
