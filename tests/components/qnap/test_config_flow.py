"""Test the QNAP config flow."""

from unittest.mock import MagicMock

import pytest
from requests.exceptions import ConnectTimeout

from homeassistant import config_entries
from homeassistant.components.qnap import const
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_HOST, TEST_PASSWORD, TEST_SERIAL, TEST_USERNAME

from tests.common import MockConfigEntry

STANDARD_CONFIG = {
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
    CONF_HOST: TEST_HOST,
}

ENTRY_DATA = {
    CONF_HOST: TEST_HOST,
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
    CONF_SSL: const.DEFAULT_SSL,
    CONF_VERIFY_SSL: const.DEFAULT_VERIFY_SSL,
    CONF_PORT: const.DEFAULT_PORT,
}


pytestmark = pytest.mark.usefixtures("mock_setup_entry", "qnap_connect")


async def test_config_flow(hass: HomeAssistant, qnap_connect: MagicMock) -> None:
    """Config flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    qnap_connect.get_system_stats.side_effect = ConnectTimeout("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    qnap_connect.get_system_stats.side_effect = TypeError("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    qnap_connect.get_system_stats.side_effect = Exception("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}

    qnap_connect.get_system_stats.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test NAS name"
    assert result["data"] == ENTRY_DATA


async def test_reconfigure_flow(hass: HomeAssistant, qnap_connect: MagicMock) -> None:
    """Test reconfigure flow updates the config entry."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_SERIAL,
        data=ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**STANDARD_CONFIG, CONF_HOST: "5.6.7.8"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "5.6.7.8"


async def test_reconfigure_cannot_connect(
    hass: HomeAssistant, qnap_connect: MagicMock
) -> None:
    """Test reconfigure flow shows error on connection timeout."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_SERIAL,
        data=ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    qnap_connect.get_system_stats.side_effect = ConnectTimeout("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_invalid_auth(
    hass: HomeAssistant, qnap_connect: MagicMock
) -> None:
    """Test reconfigure flow shows error on invalid auth."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_SERIAL,
        data=ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    qnap_connect.get_system_stats.side_effect = TypeError("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_unknown_error(
    hass: HomeAssistant, qnap_connect: MagicMock
) -> None:
    """Test reconfigure flow shows error on unknown exception."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_SERIAL,
        data=ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    qnap_connect.get_system_stats.side_effect = Exception("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "unknown"}


async def test_reconfigure_unique_id_mismatch(
    hass: HomeAssistant, qnap_connect: MagicMock
) -> None:
    """Test reconfigure aborts when serial number doesn't match."""
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_SERIAL,
        data=ENTRY_DATA,
    )
    entry.add_to_hass(hass)

    qnap_connect.get_system_stats.return_value = {
        "system": {"serial_number": "DIFFERENT_SERIAL", "name": "Other NAS"}
    }

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data[CONF_HOST] == TEST_HOST
