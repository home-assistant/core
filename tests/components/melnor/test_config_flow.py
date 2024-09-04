"""Test the melnor config flow."""

from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.melnor.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    FAKE_ADDRESS_1,
    FAKE_SERVICE_INFO_1,
    FAKE_SERVICE_INFO_2,
    patch_async_discovered_service_info,
)


async def test_user_step_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle no devices found."""
    with patch_async_discovered_service_info([]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"

        mock_setup_entry.assert_not_called()


async def test_user_step_discovered_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we properly handle device picking."""

    with patch_async_discovered_service_info([FAKE_SERVICE_INFO_1]):
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

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: FAKE_ADDRESS_1}
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["data"] == {CONF_ADDRESS: FAKE_ADDRESS_1}

    mock_setup_entry.assert_called_once()


async def test_user_step_with_existing_device(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we properly handle device picking."""

    with patch_async_discovered_service_info(
        [FAKE_SERVICE_INFO_1, FAKE_SERVICE_INFO_2]
    ):
        # Create the config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_BLUETOOTH,
                "step_id": "bluetooth_confirm",
                "user_input": {CONF_MAC: FAKE_ADDRESS_1},
            },
            data=FAKE_SERVICE_INFO_1,
        )

        # And create an entry
        await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

        mock_setup_entry.reset_mock()

        # Now open the picker and validate the current address isn't valid
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        assert result["type"] is FlowResultType.FORM

        with pytest.raises(vol.Invalid):
            await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ADDRESS: FAKE_ADDRESS_1}
            )

        mock_setup_entry.assert_not_called()


async def test_bluetooth_discovered(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we short circuit to config entry creation."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=FAKE_SERVICE_INFO_1,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": FAKE_ADDRESS_1}

    mock_setup_entry.assert_not_called()


async def test_bluetooth_confirm(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we short circuit to config entry creation."""

    # Create the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_BLUETOOTH,
            "step_id": "bluetooth_confirm",
            "user_input": {CONF_MAC: FAKE_ADDRESS_1},
        },
        data=FAKE_SERVICE_INFO_1,
    )

    # Interact with it like a user would
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == FAKE_ADDRESS_1
    assert result2["data"] == {CONF_ADDRESS: FAKE_ADDRESS_1}

    mock_setup_entry.assert_called_once()
