"""Test init of Nut integration."""

from unittest.mock import patch

from aionut import NUTError, NUTLoginError

from homeassistant.components.nut.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .util import _get_mock_nutclient, async_init_integration

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test a successful setup entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "mock", CONF_PORT: "mock"},
    )
    entry.add_to_hass(hass)

    mock_pynut = _get_mock_nutclient(
        list_ups={"ups1": "UPS 1"}, list_vars={"ups.status": "OL"}
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert entry.state is ConfigEntryState.LOADED

        state = hass.states.get("sensor.ups1_status_data")
        assert state is not None
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "OL"

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED
        assert not hass.data.get(DOMAIN)


async def test_config_not_ready(hass: HomeAssistant) -> None:
    """Test for setup failure if connection to broker is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "mock", CONF_PORT: "mock"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient.list_ups",
            return_value={"ups1"},
        ),
        patch(
            "homeassistant.components.nut.AIONUTClient.list_vars",
            side_effect=NUTError,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_auth_fails(hass: HomeAssistant) -> None:
    """Test for setup failure if auth has changed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "mock", CONF_PORT: "mock"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient.list_ups",
            return_value={"ups1"},
        ),
        patch(
            "homeassistant.components.nut.AIONUTClient.list_vars",
            side_effect=NUTLoginError,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_serial_number(hass: HomeAssistant) -> None:
    """Test for serial number set on device."""
    mock_serial_number = "A00000000000"
    await async_init_integration(
        hass,
        username="someuser",
        password="somepassword",
        list_vars={"ups.serial": mock_serial_number},
        list_ups={"ups1": "UPS 1"},
        list_commands_return_value=[],
    )

    device_registry = dr.async_get(hass)
    assert device_registry is not None

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_serial_number)}
    )

    assert device_entry is not None
    assert device_entry.serial_number == mock_serial_number


async def test_device_location(hass: HomeAssistant) -> None:
    """Test for suggested location on device."""
    mock_serial_number = "A00000000000"
    mock_device_location = "XYZ Location"
    await async_init_integration(
        hass,
        username="someuser",
        password="somepassword",
        list_vars={
            "ups.serial": mock_serial_number,
            "device.location": mock_device_location,
        },
        list_ups={"ups1": "UPS 1"},
        list_commands_return_value=[],
    )

    device_registry = dr.async_get(hass)
    assert device_registry is not None

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_serial_number)}
    )

    assert device_entry is not None
    assert device_entry.suggested_area == mock_device_location
