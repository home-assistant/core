"""Tests for the init module."""
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
from pyvesync import VeSync
from syrupy import SnapshotAssertion

from homeassistant.components.vesync import async_setup_entry
from homeassistant.components.vesync.const import (
    DOMAIN,
    SERVICE_UPDATE_DEVS,
    VS_FANS,
    VS_LIGHTS,
    VS_MANAGER,
    VS_SENSORS,
    VS_SWITCHES,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .common import get_entities, get_states


async def test_async_setup_entry__not_login(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup does not create config entry when not logged in."""
    manager.login = Mock(return_value=False)

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as setup_mock, patch(
        "homeassistant.components.vesync.async_process_devices"
    ) as process_mock, patch.object(
        hass.services, "async_register"
    ) as register_mock:
        assert not await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()
        assert setups_mock.call_count == 0
        assert setup_mock.call_count == 0
        assert process_mock.call_count == 0
        assert register_mock.call_count == 0

    assert manager.login.call_count == 1
    assert DOMAIN not in hass.data
    assert "Unable to login to the VeSync server" in caplog.text


async def test_async_setup_entry__no_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync
) -> None:
    """Test setup connects to vesync and creates empty config when no devices."""
    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as setup_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert setups_mock.call_args.args[1] == []
        assert setup_mock.call_count == 0

    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert not hass.data[DOMAIN][VS_FANS]
    assert not hass.data[DOMAIN][VS_LIGHTS]
    assert not hass.data[DOMAIN][VS_SENSORS]
    assert not hass.data[DOMAIN][VS_SWITCHES]


async def test_async_setup_entry__with_devices(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager_devices: VeSync,
) -> None:
    """Test setup connects to vesync and loads fan platform."""
    with patch.object(
        hass,
        "async_add_executor_job",
        new=AsyncMock(),
    ) as mock_add_executor_job, patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.services, "async_register"
    ) as register_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()

        assert mock_add_executor_job.call_count == 2
        assert mock_add_executor_job.call_args_list == [
            call(manager_devices.login),
            call(manager_devices.update),
        ]
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert list(setups_mock.call_args.args[1]) == [
            Platform.SWITCH,
            Platform.FAN,
            Platform.LIGHT,
            Platform.SENSOR,
        ]
        assert register_mock.call_count == 1
        assert register_mock.call_args.args[0] == DOMAIN
        assert register_mock.call_args.args[1] == SERVICE_UPDATE_DEVS
        assert callable(register_mock.call_args.args[2])

    assert hass.data[DOMAIN][VS_MANAGER] == manager_devices
    assert len(hass.data[DOMAIN][VS_FANS]) == 1
    assert len(hass.data[DOMAIN][VS_LIGHTS]) == 2
    assert len(hass.data[DOMAIN][VS_SENSORS]) == 2
    assert len(hass.data[DOMAIN][VS_SWITCHES]) == 2


async def test_asynch_setup_entry__loaded_state(
    hass: HomeAssistant,
    setup_platform,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the resulting setup state is as expected."""

    # fan devices
    states = {}
    identifier = "air-purifier"
    entities = get_entities(hass, identifier)
    assert len(entities) == 3
    states[identifier] = get_states(hass, entities)

    identifier = "asd_sdfKIHG7IJHGwJGJ7GJ_ag5h3G55"
    entities = get_entities(hass, identifier)
    assert len(entities) == 2
    states[identifier] = get_states(hass, entities)

    identifier = "400s-purifier"
    entities = get_entities(hass, identifier)
    assert len(entities) == 4
    states[identifier] = get_states(hass, entities)

    identifier = "600s-purifier"
    entities = get_entities(hass, identifier)
    assert len(entities) == 4
    states[identifier] = get_states(hass, entities)

    assert states == snapshot(name="fans")

    # bulb devices
    states = {}
    identifier = "dimmable-bulb"
    entities = get_entities(hass, identifier)
    assert len(entities) == 1
    states[identifier] = get_states(hass, entities)

    identifier = "tunable-bulb"
    entities = get_entities(hass, identifier)
    assert len(entities) == 1
    states[identifier] = get_states(hass, entities)

    assert states == snapshot(name="bulbs")

    # outlet devices
    states = {}
    identifier = "outlet"
    entities = get_entities(hass, identifier)
    assert len(entities) == 7
    states[identifier] = get_states(hass, entities)

    assert states == snapshot(name="outlets")

    # switch devices
    states = {}
    identifier = "dimmable-switch"
    entities = get_entities(hass, identifier)
    assert len(entities) == 1
    states[identifier] = get_states(hass, entities)

    assert states == snapshot(name="switches")
