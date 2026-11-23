"""Test WiZ diagnostics."""

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.wiz.const import CONF_SIGNING_KEY
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import FAKE_IP, async_setup_integration


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    _, entry = await async_setup_integration(hass)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot


async def test_diagnostics_redacts_signing_key(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the signing key is redacted from diagnostics."""
    _, entry = await async_setup_integration(
        hass,
        data={CONF_HOST: FAKE_IP, CONF_SIGNING_KEY: "00112233445566778899aabbccddeeff"},
    )

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["entry"]["data"][CONF_SIGNING_KEY] == "**REDACTED**"
