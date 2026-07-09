"""Tests for Overkiz integration init."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
from pyoverkiz.exceptions import (
    MaintenanceError,
    ServiceUnavailableError,
    TooManyRequestsError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import MockOverkizClient
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


async def test_setup_rexel_local_uses_local_client(
    hass: HomeAssistant,
    mock_rexel_local_config_entry: MockConfigEntry,
    mock_client: MockOverkizClient,
) -> None:
    """A Rexel gateway configured via the Local API must not use OAuth2."""
    mock_rexel_local_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.overkiz.create_local_client",
            return_value=mock_client,
        ) as mock_create_local_client,
        patch(
            "homeassistant.components.overkiz.create_rexel_client"
        ) as mock_create_rexel_client,
    ):
        await hass.config_entries.async_setup(mock_rexel_local_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_create_local_client.assert_called_once_with(
        hass,
        host="gateway-1234-5678-9123.local:8443",
        token="1234123412341234",
        verify_ssl=True,
    )
    mock_create_rexel_client.assert_not_called()
    assert mock_rexel_local_config_entry.state is ConfigEntryState.LOADED


async def test_go_to_alias_button_unique_id_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: MockOverkizClient,
) -> None:
    """Test migration of the legacy goToAlias button unique_id.

    Devices without core:SupportedAliases lose their legacy button; devices
    with an alias keep it, renamed to the per-alias unique_id.
    """
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_SERVER},
        minor_version=2,
    )
    mock_entry.add_to_hass(hass)

    pergola_button = entity_registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        "ogp://1234-1234-6233/10943109-goToAlias",
        config_entry=mock_entry,
    )
    venetian_blind_button = entity_registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        "ogp://1234-1234-6233/16730100-goToAlias",
        config_entry=mock_entry,
    )

    mock_client.set_setup_fixture("setup/cloud_somfy_tahoma_v2_europe.json")

    with patch(
        "homeassistant.components.overkiz.create_cloud_client",
        return_value=mock_client,
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get(pergola_button.entity_id) is None
    assert (
        entry := entity_registry.async_get(venetian_blind_button.entity_id)
    ) is not None
    assert entry.unique_id == "ogp://1234-1234-6233/16730100-goToAlias_1"
    assert mock_entry.minor_version == 3


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


@pytest.mark.parametrize(
    "exception",
    [
        OAuth2TokenRequestError(request_info=MagicMock(), domain=DOMAIN),
        TooManyRequestsError("Too many requests"),
        MaintenanceError("Server is down for maintenance"),
        ServiceUnavailableError("Server is unavailable"),
        TimeoutError("Timed out"),
        ClientError("Connection error"),
    ],
    ids=[
        "oauth2_token_request",
        "too_many_requests",
        "maintenance",
        "service_unavailable",
        "timeout",
        "client_error",
    ],
)
async def test_setup_transient_error_retries(
    hass: HomeAssistant,
    mock_rexel_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """A recoverable error during setup retries instead of failing."""
    mock_rexel_config_entry.add_to_hass(hass)

    client = AsyncMock()
    client.login.side_effect = exception

    with patch(
        "homeassistant.components.overkiz.create_rexel_client", return_value=client
    ):
        await hass.config_entries.async_setup(mock_rexel_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_rexel_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()
