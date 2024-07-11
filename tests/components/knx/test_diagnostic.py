"""Tests for the diagnostics data provided by the KNX integration."""

import pytest
from syrupy import SnapshotAssertion
from xknx.io import DEFAULT_MCAST_GRP, DEFAULT_MCAST_PORT

from homeassistant.components.knx.const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_DEFAULT_RATE_LIMIT,
    CONF_KNX_DEFAULT_STATE_UPDATER,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_KNXKEY_PASSWORD,
    CONF_KNX_MCAST_GRP,
    CONF_KNX_MCAST_PORT,
    CONF_KNX_RATE_LIMIT,
    CONF_KNX_ROUTING_BACKBONE_KEY,
    CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
    CONF_KNX_SECURE_USER_PASSWORD,
    CONF_KNX_STATE_UPDATER,
    DEFAULT_ROUTING_IA,
    DOMAIN as KNX_DOMAIN,
)
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize("hass_config", [{}])
@pytest.mark.usefixtures("mock_hass_config")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    knx: KNXTestKit,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await knx.setup_integration({})

    # Overwrite the version for this test since we don't want to change this with every library bump
    knx.xknx.version = "0.0.0"
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


@pytest.mark.parametrize("hass_config", [{"knx": {"wrong_key": {}}}])
@pytest.mark.usefixtures("mock_hass_config")
async def test_diagnostic_config_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    knx: KNXTestKit,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await knx.setup_integration({})

    # Overwrite the version for this test since we don't want to change this with every library bump
    knx.xknx.version = "0.0.0"
    # the snapshot will contain 'configuration_error' key with the voluptuous error message
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


@pytest.mark.parametrize("hass_config", [{}])
@pytest.mark.usefixtures("mock_hass_config")
async def test_diagnostic_redact(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics redacting data."""
    mock_config_entry: MockConfigEntry = MockConfigEntry(
        title="KNX",
        domain=KNX_DOMAIN,
        data={
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            CONF_KNX_RATE_LIMIT: CONF_KNX_DEFAULT_RATE_LIMIT,
            CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
            CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_INDIVIDUAL_ADDRESS: DEFAULT_ROUTING_IA,
            CONF_KNX_KNXKEY_PASSWORD: "password",
            CONF_KNX_SECURE_USER_PASSWORD: "user_password",
            CONF_KNX_SECURE_DEVICE_AUTHENTICATION: "device_authentication",
            CONF_KNX_ROUTING_BACKBONE_KEY: "bbaacc44bbaacc44bbaacc44bbaacc44",
        },
    )
    knx: KNXTestKit = KNXTestKit(hass, mock_config_entry)
    await knx.setup_integration({})

    # Overwrite the version for this test since we don't want to change this with every library bump
    knx.xknx.version = "0.0.0"
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


@pytest.mark.parametrize("hass_config", [{}])
@pytest.mark.usefixtures("mock_hass_config")
async def test_diagnostics_project(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    knx: KNXTestKit,
    load_knxproj: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await knx.setup_integration({})
    knx.xknx.version = "0.0.0"
    # snapshot will contain project specific fields in `project_info`
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
