"""Tests for Overkiz integration init."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

from pyoverkiz.client import OverkizClient
from pyoverkiz.enums import Server
import pytest

from homeassistant import config_entries
from homeassistant.components.overkiz import create_cloud_client, create_local_client
from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .test_config_flow import TEST_EMAIL, TEST_GATEWAY_ID, TEST_PASSWORD, TEST_SERVER

from tests.common import MockConfigEntry, RegistryEntryWithDefaults, mock_registry

ENTITY_SENSOR_DISCRETE_RSSI_LEVEL = "sensor.zipscreen_woonkamer_discrete_rssi_level"
ENTITY_ALARM_CONTROL_PANEL = "alarm_control_panel.alarm"
ENTITY_SWITCH_GARAGE = "switch.garage"
ENTITY_SENSOR_TARGET_CLOSURE_STATE = "sensor.zipscreen_woonkamer_target_closure_state"
ENTITY_SENSOR_TARGET_CLOSURE_STATE_2 = (
    "sensor.zipscreen_woonkamer_target_closure_state_2"
)


async def test_unique_id_migration(hass: HomeAssistant) -> None:
    """Test migration of sensor unique IDs."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_SERVER},
        minor_version=1,
    )

    mock_entry.add_to_hass(hass)

    mock_registry(
        hass,
        {
            # This entity will be migrated to "io://1234-5678-1234/3541212-core:DiscreteRSSILevelState"
            ENTITY_SENSOR_DISCRETE_RSSI_LEVEL: RegistryEntryWithDefaults(
                entity_id=ENTITY_SENSOR_DISCRETE_RSSI_LEVEL,
                unique_id="io://1234-5678-1234/3541212-OverkizState.CORE_DISCRETE_RSSI_LEVEL",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            # This entity will be migrated to "internal://1234-5678-1234/alarm/0-TSKAlarmController"
            ENTITY_ALARM_CONTROL_PANEL: RegistryEntryWithDefaults(
                entity_id=ENTITY_ALARM_CONTROL_PANEL,
                unique_id="internal://1234-5678-1234/alarm/0-UIWidget.TSKALARM_CONTROLLER",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            # This entity will be migrated to "io://1234-5678-1234/0-OnOff"
            ENTITY_SWITCH_GARAGE: RegistryEntryWithDefaults(
                entity_id=ENTITY_SWITCH_GARAGE,
                unique_id="io://1234-5678-1234/0-UIClass.ON_OFF",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            # This entity will be removed since
            # "io://1234-5678-1234/3541212-core:TargetClosureState"
            # already exists
            ENTITY_SENSOR_TARGET_CLOSURE_STATE: RegistryEntryWithDefaults(
                entity_id=ENTITY_SENSOR_TARGET_CLOSURE_STATE,
                unique_id="io://1234-5678-1234/3541212-OverkizState.CORE_TARGET_CLOSURE",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            # This entity will not be migrated"
            ENTITY_SENSOR_TARGET_CLOSURE_STATE_2: RegistryEntryWithDefaults(
                entity_id=ENTITY_SENSOR_TARGET_CLOSURE_STATE_2,
                unique_id="io://1234-5678-1234/3541212-core:TargetClosureState",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    unique_id_map = {
        ENTITY_SENSOR_DISCRETE_RSSI_LEVEL: "io://1234-5678-1234/3541212-core:DiscreteRSSILevelState",
        ENTITY_ALARM_CONTROL_PANEL: "internal://1234-5678-1234/alarm/0-TSKAlarmController",
        ENTITY_SWITCH_GARAGE: "io://1234-5678-1234/0-OnOff",
        ENTITY_SENSOR_TARGET_CLOSURE_STATE_2: "io://1234-5678-1234/3541212-core:TargetClosureState",
    }

    # Test if entities will be removed
    assert set(ent_reg.entities.keys()) == set(unique_id_map)

    # Test if unique ids are migrated
    for entity_id, unique_id in unique_id_map.items():
        entry = ent_reg.async_get(entity_id)
        assert entry.unique_id == unique_id

    # Test if the config entry is migrated to the latest minor version
    assert mock_entry.minor_version == 2


async def test_setup_token_reauth_error_starts_reauth(
    hass: HomeAssistant, mock_rexel_config_entry: MockConfigEntry
) -> None:
    """A non-recoverable token refresh failure triggers reauth."""
    mock_rexel_config_entry.add_to_hass(hass)

    client = AsyncMock()
    client.login.side_effect = OAuth2TokenRequestReauthError(
        request_info=MagicMock(), domain=DOMAIN
    )

    with patch(
        "homeassistant.components.overkiz.create_rexel_client", return_value=client
    ):
        await hass.config_entries.async_setup(mock_rexel_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_rexel_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH


async def test_setup_token_transient_error_retries(
    hass: HomeAssistant, mock_rexel_config_entry: MockConfigEntry
) -> None:
    """A recoverable token refresh failure retries setup."""
    mock_rexel_config_entry.add_to_hass(hass)

    client = AsyncMock()
    client.login.side_effect = OAuth2TokenRequestError(
        request_info=MagicMock(), domain=DOMAIN
    )

    with patch(
        "homeassistant.components.overkiz.create_rexel_client", return_value=client
    ):
        await hass.config_entries.async_setup(mock_rexel_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_rexel_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize(
    "create_client",
    [
        lambda hass: create_cloud_client(
            hass, TEST_EMAIL, TEST_PASSWORD, Server.SOMFY_EUROPE
        ),
        lambda hass: create_local_client(hass, "192.168.1.2", "token", verify_ssl=True),
    ],
    ids=["cloud", "local"],
)
async def test_client_enables_action_queue(
    hass: HomeAssistant,
    create_client: Callable[[HomeAssistant], OverkizClient],
) -> None:
    """Test the client factories enable the action queue.

    The queue merges the bursts of action groups produced when an automation or
    scene drives many devices at once into a single execution, which the gateway
    would otherwise reject with a rate-limit error.
    """
    client = create_client(hass)

    assert client.settings.action_queue is not None
