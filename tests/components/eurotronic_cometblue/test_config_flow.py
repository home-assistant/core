"""Test the eurotronic_cometblue config flow."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from bleak.exc import BleakDeviceNotFoundError
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.eurotronic_cometblue.config_flow import (
    name_from_discovery,
)
from homeassistant.components.eurotronic_cometblue.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import FIXTURE_DEVICE_NAME, FIXTURE_MAC, FIXTURE_USER_INPUT
from .conftest import FAKE_SERVICE_INFO

from tests.common import MockConfigEntry


async def test_user_step_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle no devices found."""
    with patch(
        "homeassistant.components.eurotronic_cometblue.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"

        mock_setup_entry.assert_not_called()


async def test_user_step_discovered_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_service_info: None
) -> None:
    """Test we properly handle device picking."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_device"

    with pytest.raises(vol.Invalid):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: "wrong_address"}
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ADDRESS: FIXTURE_MAC}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=FIXTURE_USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == f"{FIXTURE_DEVICE_NAME} {FIXTURE_MAC}"
    assert result["result"].unique_id == FIXTURE_MAC
    assert result["result"].data == {
        CONF_ADDRESS: FIXTURE_MAC,
        CONF_PIN: FIXTURE_USER_INPUT[CONF_PIN],
    }
    mock_setup_entry.assert_called_once()


async def test_user_step_with_existing_device(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test we properly handle device picking if entry exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=FAKE_SERVICE_INFO,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_setup_entry.call_count == 0


async def test_bluetooth_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we can handle a bluetooth discovery flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=FAKE_SERVICE_INFO,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        FIXTURE_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == f"{FIXTURE_DEVICE_NAME} {FIXTURE_MAC}"
    assert result["result"].unique_id == FIXTURE_MAC
    assert result["result"].data == {
        CONF_ADDRESS: FIXTURE_MAC,
        CONF_PIN: FIXTURE_USER_INPUT[CONF_PIN],
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("patch_target", "side_effect", "expected_error"),
    [
        (
            "get_battery_async",
            TimeoutError(),
            {"base": "invalid_pin"},
        ),
        (
            "connect_async",
            TimeoutError(),
            {"base": "timeout_connect"},
        ),
        (
            "connect_async",
            BleakDeviceNotFoundError(FAKE_SERVICE_INFO.address),
            {"base": "cannot_connect"},
        ),
        (
            "connect_async",
            OSError("Something totally unexpected"),
            {"base": "unknown"},
        ),
    ],
)
async def test_bluetooth_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    patch_target: str,
    side_effect: Exception,
    expected_error: dict,
) -> None:
    """Test we can handle a bluetooth discovery flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=FAKE_SERVICE_INFO,
    )

    with patch(
        f"homeassistant.components.eurotronic_cometblue.config_flow.AsyncCometBlue.{patch_target}",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == expected_error

    # now retry without side effect, simulating a user correcting the issue (e.g. entering correct PIN)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        FIXTURE_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == f"{FIXTURE_DEVICE_NAME} {FIXTURE_MAC}"
    assert result["result"].unique_id == FIXTURE_MAC
    assert result["result"].data == {
        CONF_ADDRESS: FIXTURE_MAC,
        CONF_PIN: FIXTURE_USER_INPUT[CONF_PIN],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_flow_no_device(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we can handle a bluetooth discovery flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=FAKE_SERVICE_INFO,
    )

    with patch(
        "homeassistant.components.eurotronic_cometblue.config_flow.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_name_from_discovery() -> None:
    """Test we can create a name from discovery info."""
    # If for some reason no name can be derived, just return the default name
    assert name_from_discovery(None) == "Comet Blue"

    # If the name is the same as the address, just return the address to avoid long names
    fake_info = deepcopy(FAKE_SERVICE_INFO)
    fake_info.name = str(fake_info.address)
    assert name_from_discovery(fake_info) == str(fake_info.address)

    fake_info = deepcopy(FAKE_SERVICE_INFO)
    assert name_from_discovery(fake_info) == f"{FIXTURE_DEVICE_NAME} {FIXTURE_MAC}"
