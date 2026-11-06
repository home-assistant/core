"""Tests for the diagnostics data provided by the Yeelight integration."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.yeelight.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import CONFIG_ENTRY_DATA, IP_ADDRESS, MODULE, _mocked_bulb, _patch_discovery


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS, **CONFIG_ENTRY_DATA}
    )
    config_entry.add_to_hass(hass)

    with (
        _patch_discovery(),
        patch(f"{MODULE}.AsyncBulb", return_value=_mocked_bulb()),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )


async def test_diagnostics_unknown_device_type(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test diagnostics for a device with an unknown type."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS, **CONFIG_ENTRY_DATA}
    )
    config_entry.add_to_hass(hass)
    mocked_bulb = _mocked_bulb()
    mocked_bulb.bulb_type = None

    with (
        _patch_discovery(),
        patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert diagnostics["device"]["type"] is None
