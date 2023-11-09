"""The sensor tests for the nut platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.nut.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_RESOURCES,
    PERCENTAGE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .util import _get_mock_pynutclient, async_init_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "model",
    [
        "PR3000RT2U",
        "CP1350C",
        "5E850I",
        "5E650I",
        "BACKUPSES600M1",
        "DL650ELCD",
        "EATON5P1550",
        "blazer_usb",
    ],
)
async def test_devices(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, model: str
) -> None:
    """Test creation of device sensors."""

    config_entry = await async_init_integration(hass, model)
    entry = entity_registry.async_get("sensor.ups1_battery_charge")
    assert entry
    assert entry.config_entry_id == config_entry.entry_id

    state = hass.states.get("sensor.ups1_battery_charge")
    assert state.state == "100"

    expected_attributes = {
        "device_class": "battery",
        "friendly_name": "Ups1 Battery charge",
        "unit_of_measurement": PERCENTAGE,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == attr for key, attr in expected_attributes.items()
    )


async def test_state_sensors(hass: HomeAssistant) -> None:
    """Test creation of status display sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "mock", CONF_PORT: "mock"},
    )
    entry.add_to_hass(hass)

    mock_pynut = _get_mock_pynutclient(
        list_ups={"ups1": "UPS 1"}, list_vars={"ups.status": "OL"}
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state1 = hass.states.get("sensor.ups1_status")
        state2 = hass.states.get("sensor.ups1_status_data")
        assert state1.state == "Online"
        assert state2.state == "OL"


async def test_unknown_state_sensors(hass: HomeAssistant) -> None:
    """Test creation of unknown status display sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "mock", CONF_PORT: "mock"},
    )
    entry.add_to_hass(hass)

    mock_pynut = _get_mock_pynutclient(
        list_ups={"ups1": "UPS 1"}, list_vars={"ups.status": "OQ"}
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state1 = hass.states.get("sensor.ups1_status")
        state2 = hass.states.get("sensor.ups1_status_data")
        assert state1.state == STATE_UNKNOWN
        assert state2.state == "OQ"


async def test_stale_options(hass: HomeAssistant) -> None:
    """Test creation of sensors with stale options to remove."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "mock",
            CONF_PORT: "mock",
            CONF_RESOURCES: ["ups.load"],
        },
        options={CONF_RESOURCES: ["battery.charge"]},
    )
    config_entry.add_to_hass(hass)

    mock_pynut = _get_mock_pynutclient(
        list_ups={"ups1": "UPS 1"}, list_vars={"battery.charge": "10"}
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        entry = registry.async_get("sensor.ups1_battery_charge")
        assert entry
        assert entry.unique_id == f"{config_entry.entry_id}_battery.charge"
        assert config_entry.data[CONF_RESOURCES] == ["battery.charge"]
        assert config_entry.options == {}

        state = hass.states.get("sensor.ups1_battery_charge")
        assert state.state == "10"
