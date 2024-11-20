"""Tests for the One-Time Password (OTP) Sensors."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.otp.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_pyotp")
async def test_setup(
    hass: HomeAssistant,
    otp_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of ista EcoTrend sensor platform."""

    otp_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(otp_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.otp_sensor") == snapshot


async def test_deprecated_yaml_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, otp_yaml_config: ConfigType
) -> None:
    """Test an issue is created when attempting setup from yaml config."""

    assert await async_setup_component(hass, SENSOR_DOMAIN, otp_yaml_config)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN, issue_id=f"deprecated_yaml_{DOMAIN}"
    )
