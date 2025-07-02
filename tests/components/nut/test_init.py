"""Test init of Nut integration."""

from copy import deepcopy
from unittest.mock import patch

from aionut import NUTError, NUTLoginError
import pytest

from homeassistant.components.nut.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .util import _get_mock_nutclient, async_init_integration

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_config_entry_migrations(hass: HomeAssistant) -> None:
    """Test that config entries were migrated."""
    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage"},
        list_ups={"ups1": "UPS 1"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 123,
            },
            options={CONF_SCAN_INTERVAL: 30},
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)

        assert CONF_SCAN_INTERVAL not in entry.options


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


async def test_remove_device_valid(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that we cannot remove a device that still exists."""
    assert await async_setup_component(hass, "config", {})

    mock_serial_number = "A00000000000"
    config_entry = await async_init_integration(
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

    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, config_entry.entry_id)
    assert not response["success"]


async def test_remove_device_stale(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that we can remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})

    mock_serial_number = "A00000000000"
    config_entry = await async_init_integration(
        hass,
        username="someuser",
        password="somepassword",
        list_vars={"ups.serial": mock_serial_number},
        list_ups={"ups1": "UPS 1"},
        list_commands_return_value=[],
    )

    device_registry = dr.async_get(hass)
    assert device_registry is not None

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "remove-device-id")},
    )

    assert device_entry is not None

    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, config_entry.entry_id)
    assert response["success"]

    # Verify that device entry is removed
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "remove-device-id")}
    )
    assert device_entry is None


async def test_config_not_ready(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for setup failure if connection to broker is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "mock", CONF_PORT: "mock"},
    )
    entry.add_to_hass(hass)

    nut_error_message = "Something wrong happened"
    error_message = f"Error fetching UPS state: {nut_error_message}"
    with (
        patch(
            "homeassistant.components.nut.AIONUTClient.list_ups",
            return_value={"ups1"},
        ),
        patch(
            "homeassistant.components.nut.AIONUTClient.list_vars",
            side_effect=NUTError(nut_error_message),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY

        assert error_message in caplog.text


async def test_auth_fails(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for setup failure if auth has changed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "mock", CONF_PORT: "mock"},
    )
    entry.add_to_hass(hass)

    nut_error_message = "Something wrong happened"
    error_message = f"Device authentication error: {nut_error_message}"
    with (
        patch(
            "homeassistant.components.nut.AIONUTClient.list_ups",
            return_value={"ups1"},
        ),
        patch(
            "homeassistant.components.nut.AIONUTClient.list_vars",
            side_effect=NUTLoginError(nut_error_message),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_ERROR

        assert error_message in caplog.text

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_serial_number(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
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

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_serial_number)}
    )

    assert device_entry is not None
    assert device_entry.serial_number == mock_serial_number


async def test_device_location(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
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

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_serial_number)}
    )

    assert device_entry is not None
    assert device_entry.suggested_area == mock_device_location


async def test_update_options(hass: HomeAssistant) -> None:
    """Test update options triggers reload."""
    mock_pynut = _get_mock_nutclient(
        list_ups={"ups1": "UPS 1"}, list_vars={"ups.status": "OL"}
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        mock_config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "mock",
                CONF_PASSWORD: "somepassword",
                CONF_PORT: "mock",
                CONF_USERNAME: "someuser",
            },
            options={
                "device_options": {
                    "fake_option": "fake_option_value",
                },
            },
        )
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert mock_config_entry.state is ConfigEntryState.LOADED

        new_options = deepcopy(dict(mock_config_entry.options))
        new_options["device_options"].clear()
        hass.config_entries.async_update_entry(mock_config_entry, options=new_options)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED
