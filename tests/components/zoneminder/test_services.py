"""Tests for ZoneMinder service calls."""

from unittest.mock import MagicMock, patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.components.zoneminder.services import ZoneMinderServiceArgument
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import setup_integration
from .conftest import (
    MOCK_CONFIG_DATA,
    MOCK_HOST,
    MOCK_HOST_2,
    MOCK_OPTIONS,
    create_mock_monitor,
    create_mock_zm_client,
)


async def test_set_run_state(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set_run_state sets the state on the ZoneMinder server."""
    await setup_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {
            ZoneMinderServiceArgument.ID: MOCK_HOST,
            ZoneMinderServiceArgument.NAME: "Away",
        },
        blocking=True,
    )

    mock_zoneminder_client.set_active_state.assert_called_once_with("Away")


async def test_set_run_state_multi_server(hass: HomeAssistant) -> None:
    """Test set_run_state targets the server matching the host."""
    client_1 = create_mock_zm_client([create_mock_monitor()])
    client_2 = create_mock_zm_client([create_mock_monitor()])
    entry_1 = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_DATA, options=MOCK_OPTIONS
    )
    entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG_DATA, CONF_HOST: MOCK_HOST_2},
        options=MOCK_OPTIONS,
    )

    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        side_effect=[client_1, client_2],
    ):
        await setup_integration(hass, entry_1, [Platform.BINARY_SENSOR])
        await setup_integration(hass, entry_2, [Platform.BINARY_SENSOR])

    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {
            ZoneMinderServiceArgument.ID: MOCK_HOST_2,
            ZoneMinderServiceArgument.NAME: "Home",
        },
        blocking=True,
    )

    client_2.set_active_state.assert_called_once_with("Home")
    client_1.set_active_state.assert_not_called()


@pytest.mark.usefixtures("mock_zoneminder_client")
async def test_set_run_state_missing_fields(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a service call with missing required fields is rejected."""
    await setup_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    with pytest.raises(probatio.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            "set_run_state",
            {
                ZoneMinderServiceArgument.ID: MOCK_HOST
            },  # Missing ZoneMinderServiceArgument.NAME
            blocking=True,
        )


@pytest.mark.usefixtures("mock_zoneminder_client")
async def test_set_run_state_invalid_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a service call for an unknown host raises a validation error."""
    await setup_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "set_run_state",
            {
                ZoneMinderServiceArgument.ID: "invalid.host",
                ZoneMinderServiceArgument.NAME: "Away",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_host"


async def test_set_run_state_failure_logged(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed state change is logged."""
    mock_zoneminder_client.set_active_state.return_value = {}
    await setup_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {
            ZoneMinderServiceArgument.ID: MOCK_HOST,
            ZoneMinderServiceArgument.NAME: "Away",
        },
        blocking=True,
    )

    assert "Unable to change ZoneMinder state" in caplog.text
