"""Test the WWS config flow."""

from unittest.mock import AsyncMock, patch

from pyenergiedock import EdAPIError, EdAuthError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.wws.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_config_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "flow_id" in result

    # Submit login data for the user with the mocked API call
    with patch(
        "homeassistant.components.wws.config_flow.DynamiT.async_login",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": "test@wws.de",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WestfalenWIND Ökostrom smart"
    assert result["data"] == {
        "username": "test@wws.de",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_invalid_auth(
    hass: HomeAssistant,
) -> None:
    """Test invalid credentials are rejected."""
    with patch(
        "homeassistant.components.wws.config_flow.DynamiT.async_login",
        side_effect=EdAuthError("Invalid credentials"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "wrong@example.com",
                "password": "wrong-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test connection errors are handled."""
    with patch(
        "homeassistant.components.wws.config_flow.DynamiT.async_login",
        side_effect=EdAPIError("API unavailable"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test@example.com",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test integration is already configured."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="WestfalenWIND Ökostrom smart",
        data={
            "username": "test@wws.de",
            "password": "test-password",
        },
        unique_id="test@wws.de",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.wws.config_flow.DynamiT.async_login",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": "test@wws.de",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test the setup entry function."""
    mock_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        title="WestfalenWIND Ökostrom smart",
        data={
            "username": "test@wws.de",
            "password": "test-password",
        },
        unique_id="test@wws.de",
    )
    mock_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.wws.DynamiT.async_get_latest_prices",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "homeassistant.components.wws.DynamiT.async_get_latest_measurements",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)

    await hass.async_block_till_done()

    assert mock_entry.state is config_entries.ConfigEntryState.LOADED


async def test_setup_entry_fetches_data_on_startup(
    hass: HomeAssistant,
) -> None:
    """Test the initial coordinator refresh populates sensor data."""
    mock_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        title="WestfalenWIND Ökostrom smart",
        data={
            "username": "test@example.com",
            "password": "test-password",
        },
        unique_id="test@example.com",
    )

    mock_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.wws.async_get_clientsession",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.wws.coordinator.WwsCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_refresh,
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)

    mock_refresh.assert_awaited_once()
