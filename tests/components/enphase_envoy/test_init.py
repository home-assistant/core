"""Test Enphase Envoy runtime."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from jwt import encode
from pyenphase import EnvoyAuthenticationError, EnvoyError, EnvoyTokenAuth
from pyenphase.auth import EnvoyLegacyAuth
import pytest
import respx

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.enphase_envoy.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_with_pre_v7_firmware(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test enphase_envoy coordinator with pre V7 firmware."""
    mock_envoy.firmware = "5.1.1"
    mock_envoy.auth = EnvoyLegacyAuth(
        "127.0.0.1", username="test-username", password="test-password"
    )
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED

    assert (entity_state := hass.states.get("sensor.inverter_1"))
    assert entity_state.state == "1"


@pytest.mark.freeze_time("2024-07-23 00:00:00+00:00")
async def test_token_in_config_file(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
) -> None:
    """Test coordinator with token provided from config."""
    token = encode(
        payload={"name": "envoy", "exp": 1907837780},
        key="secret",
        algorithm="HS256",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e72",
        title="Envoy 1234",
        unique_id="1234",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_NAME: "Envoy 1234",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_TOKEN: token,
        },
    )
    mock_envoy.auth = EnvoyTokenAuth("127.0.0.1", token=token, envoy_serial="1234")
    await setup_integration(hass, entry)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED

    assert (entity_state := hass.states.get("sensor.inverter_1"))
    assert entity_state.state == "1"


@respx.mock
@pytest.mark.freeze_time("2024-07-23 00:00:00+00:00")
async def test_expired_token_in_config(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
) -> None:
    """Test coordinator with expired token provided from config."""
    current_token = encode(
        # some time in 2021
        payload={"name": "envoy", "exp": 1627314600},
        key="secret",
        algorithm="HS256",
    )

    # mock envoy with expired token in config
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e72",
        title="Envoy 1234",
        unique_id="1234",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_NAME: "Envoy 1234",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_TOKEN: current_token,
        },
    )
    # Make sure to mock pyenphase.auth.EnvoyTokenAuth._obtain_token
    # when specifying username and password in EnvoyTokenauth
    mock_envoy.auth = EnvoyTokenAuth(
        "127.0.0.1",
        token=current_token,
        envoy_serial="1234",
        cloud_username="test_username",
        cloud_password="test_password",
    )
    await setup_integration(hass, entry)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED

    assert (entity_state := hass.states.get("sensor.inverter_1"))
    assert entity_state.state == "1"


async def test_coordinator_update_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator update error handling."""
    await setup_integration(hass, config_entry)

    assert (entity_state := hass.states.get("sensor.inverter_1"))
    original_state = entity_state

    # force HA to detect changed data by changing raw
    mock_envoy.data.raw = {"I": "am changed 1"}
    mock_envoy.update.side_effect = EnvoyError

    # Move time to next update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (entity_state := hass.states.get("sensor.inverter_1"))
    assert entity_state.state == STATE_UNAVAILABLE

    mock_envoy.reset_mock(return_value=True, side_effect=True)

    mock_envoy.data.raw = {"I": "am changed 2"}

    # Move time to next update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (entity_state := hass.states.get("sensor.inverter_1"))
    assert entity_state.state == original_state.state


async def test_coordinator_update_authentication_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test enphase_envoy coordinator update authentication error handling."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    # force HA to detect changed data by changing raw
    mock_envoy.data.raw = {"I": "am changed 1"}
    mock_envoy.update.side_effect = EnvoyAuthenticationError("This must fail")

    # Move time to next update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (entity_state := hass.states.get("sensor.inverter_1"))
    assert entity_state.state == STATE_UNAVAILABLE


@pytest.mark.freeze_time("2024-07-23 00:00:00+00:00")
async def test_coordinator_token_refresh_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
) -> None:
    """Test coordinator with token provided from config."""
    # 63, 69-79  _async_try_refresh_token
    token = encode(
        # some time in 2021
        payload={"name": "envoy", "exp": 1627314600},
        key="secret",
        algorithm="HS256",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e72",
        title="Envoy 1234",
        unique_id="1234",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_NAME: "Envoy 1234",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_TOKEN: token,
        },
    )
    # token refresh without username and password specified in
    # EnvoyTokenAuthwill force token refresh error
    mock_envoy.auth = EnvoyTokenAuth("127.0.0.1", token=token, envoy_serial="1234")
    await setup_integration(hass, entry)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED

    assert (entity_state := hass.states.get("sensor.inverter_1"))
    assert entity_state.state == "1"
