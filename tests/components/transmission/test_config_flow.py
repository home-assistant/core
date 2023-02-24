"""Tests for Transmission config flow."""
from unittest.mock import MagicMock, patch

import pytest
from transmission_rpc.error import TransmissionError

from homeassistant import config_entries
from homeassistant.components import transmission
from homeassistant.components.transmission.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_api():
    """Mock an api."""
    with patch("transmission_rpc.Client") as api:
        yield api


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.transmission.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Transmission"
    assert result2["data"] == MOCK_CONFIG_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_device_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test aborting if the device is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_name_already_configured(hass: HomeAssistant) -> None:
    """Test name is already configured."""
    entry = MockConfigEntry(
        domain=transmission.DOMAIN,
        data=MOCK_CONFIG_DATA,
        options={"scan_interval": 120},
    )
    entry.add_to_hass(hass)

    mock_entry = MOCK_CONFIG_DATA.copy()
    mock_entry["host"] = "1.1.1.1"
    result = await hass.config_entries.flow.async_init(
        transmission.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=mock_entry,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"name": "name_exists"}


async def test_options(hass: HomeAssistant) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=transmission.DOMAIN,
        data=MOCK_CONFIG_DATA,
        options={"scan_interval": 120},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.transmission.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"scan_interval": 10}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["scan_interval"] == 10


async def test_error_on_wrong_credentials(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test we handle invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api.side_effect = TransmissionError("401: Unauthorized")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {
        "username": "invalid_auth",
        "password": "invalid_auth",
    }


async def test_error_on_connection_failure(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api.side_effect = TransmissionError("111: Connection refused")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=transmission.DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        transmission.DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG_DATA,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {"username": "user"}

    with patch(
        "homeassistant.components.transmission.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_failed(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test we can't reauth due to invalid password."""
    entry = MockConfigEntry(
        domain=transmission.DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        transmission.DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG_DATA,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {"username": "user"}

    mock_api.side_effect = TransmissionError("401: Unauthorized")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "password": "wrong-password",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"password": "invalid_auth"}


async def test_reauth_failed_connection_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test we can't reauth due to connection error."""
    entry = MockConfigEntry(
        domain=transmission.DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        transmission.DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG_DATA,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {"username": "user"}

    mock_api.side_effect = TransmissionError("111: Connection refused")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "password": "test-password",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
