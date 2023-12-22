"""Test the UptimeRobot init."""
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pyuptimerobot import UptimeRobotAuthenticationException, UptimeRobotException

from homeassistant import config_entries
from homeassistant.components.uptimerobot.const import (
    COORDINATOR_UPDATE_INTERVAL,
    DOMAIN,
)
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import (
    MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA,
    MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA_KEY_READ_ONLY,
    MOCK_UPTIMEROBOT_MONITOR,
    UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY,
    MockApiResponseKey,
    mock_uptimerobot_api_response,
    setup_uptimerobot_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_reauthentication_trigger_in_setup(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reauthentication trigger."""
    mock_config_entry = MockConfigEntry(**MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA)
    mock_config_entry.add_to_hass(hass)

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        side_effect=UptimeRobotAuthenticationException,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()

    assert mock_config_entry.state == config_entries.ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "could not authenticate"

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH
    assert flow["context"]["entry_id"] == mock_config_entry.entry_id

    assert (
        "Config entry 'test@test.test' for uptimerobot integration could not authenticate"
        in caplog.text
    )


async def test_reauthentication_trigger_key_read_only(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reauthentication trigger."""
    mock_config_entry = MockConfigEntry(
        **MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA_KEY_READ_ONLY
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()

    assert mock_config_entry.state == config_entries.ConfigEntryState.SETUP_ERROR
    assert (
        mock_config_entry.reason
        == "Wrong API key type detected, use the 'main' API key"
    )

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH
    assert flow["context"]["entry_id"] == mock_config_entry.entry_id

    assert (
        "Config entry 'test@test.test' for uptimerobot integration could not authenticate"
        in caplog.text
    )


async def test_reauthentication_trigger_after_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reauthentication trigger."""
    mock_config_entry = await setup_uptimerobot_integration(hass)

    binary_sensor = hass.states.get(UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY)
    assert mock_config_entry.state == config_entries.ConfigEntryState.LOADED
    assert binary_sensor.state == STATE_ON

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        side_effect=UptimeRobotAuthenticationException,
    ):
        freezer.tick(COORDINATOR_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert (
        hass.states.get(UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY).state
        == STATE_UNAVAILABLE
    )

    assert "Authentication failed while fetching uptimerobot data" in caplog.text

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH
    assert flow["context"]["entry_id"] == mock_config_entry.entry_id


async def test_integration_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test integration reload."""
    mock_entry = await setup_uptimerobot_integration(hass)

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        return_value=mock_uptimerobot_api_response(),
    ):
        assert await hass.config_entries.async_reload(mock_entry.entry_id)
        freezer.tick(COORDINATOR_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert entry.state == config_entries.ConfigEntryState.LOADED
    assert hass.states.get(UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY).state == STATE_ON


async def test_update_errors(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test errors during updates."""
    await setup_uptimerobot_integration(hass)

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        side_effect=UptimeRobotException,
    ):
        freezer.tick(COORDINATOR_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            hass.states.get(UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY).state
            == STATE_UNAVAILABLE
        )

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        return_value=mock_uptimerobot_api_response(),
    ):
        freezer.tick(COORDINATOR_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY).state == STATE_ON

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        return_value=mock_uptimerobot_api_response(key=MockApiResponseKey.ERROR),
    ):
        freezer.tick(COORDINATOR_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            hass.states.get(UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY).state
            == STATE_UNAVAILABLE
        )

    assert "Error fetching uptimerobot data: test error from API" in caplog.text


async def test_device_management(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that we are adding and removing devices for monitors returned from the API."""
    mock_entry = await setup_uptimerobot_integration(hass)
    dev_reg = dr.async_get(hass)

    devices = dr.async_entries_for_config_entry(dev_reg, mock_entry.entry_id)
    assert len(devices) == 1

    assert devices[0].identifiers == {(DOMAIN, "1234")}
    assert devices[0].name == "Test monitor"

    assert hass.states.get(UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY).state == STATE_ON
    assert hass.states.get(f"{UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY}_2") is None

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        return_value=mock_uptimerobot_api_response(
            data=[MOCK_UPTIMEROBOT_MONITOR, {**MOCK_UPTIMEROBOT_MONITOR, "id": 12345}]
        ),
    ):
        freezer.tick(COORDINATOR_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(dev_reg, mock_entry.entry_id)
    assert len(devices) == 2
    assert devices[0].identifiers == {(DOMAIN, "1234")}
    assert devices[1].identifiers == {(DOMAIN, "12345")}

    assert hass.states.get(UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY).state == STATE_ON
    assert (
        hass.states.get(f"{UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY}_2").state == STATE_ON
    )

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        return_value=mock_uptimerobot_api_response(),
    ):
        freezer.tick(COORDINATOR_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(dev_reg, mock_entry.entry_id)
    assert len(devices) == 1
    assert devices[0].identifiers == {(DOMAIN, "1234")}

    assert hass.states.get(UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY).state == STATE_ON
    assert hass.states.get(f"{UPTIMEROBOT_BINARY_SENSOR_TEST_ENTITY}_2") is None
