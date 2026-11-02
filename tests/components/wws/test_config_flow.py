"""Test the WWS config flow."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyenergiedock import EdAPIError, EdAuthError
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

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
    assert result["result"].unique_id == "test@wws.de"
    assert result["data"] == {
        "username": "test@wws.de",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test invalid credentials are rejected."""
    with patch(
        "homeassistant.components.wws.config_flow.DynamiT.async_login",
        new_callable=AsyncMock,
    ) as mock_login:
        mock_login.side_effect = EdAuthError("Invalid credentials")
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        flow_id = result["flow_id"]

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                "username": "wrong@example.com",
                "password": "wrong-password",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

        mock_login.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                "username": "test@wws.de",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test connection errors are handled."""
    with patch(
        "homeassistant.components.wws.config_flow.DynamiT.async_login",
        new_callable=AsyncMock,
    ) as mock_login:
        mock_login.side_effect = EdAPIError("API unavailable")
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        flow_id = result["flow_id"]

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                "username": "test@example.com",
                "password": "test-password",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

        mock_login.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                "username": "test@wws.de",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_already_configured(hass: HomeAssistant) -> None:
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
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the initial coordinator refresh creates sensors with API data."""
    freezer.move_to(datetime(2024, 1, 1, 12, 7, tzinfo=UTC))
    mock_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        title="WestfalenWIND Ökostrom smart",
        data={"username": "test@example.com", "password": "test-password"},
        unique_id="test@example.com",
    )
    mock_entry.add_to_hass(hass)
    prices = [
        {
            "start": (start := datetime(2024, 1, 1, 12, minute, tzinfo=UTC)),
            "end": start + timedelta(minutes=15),
            "price_ct_kwh": value,
        }
        for minute, value in ((0, 35), (15, 35), (30, 34), (45, 34))
    ]
    measurements = [
        {
            "start": datetime(2023, 12, 31, 12, 0, tzinfo=UTC),
            "end": datetime(2023, 12, 31, 12, 15, tzinfo=UTC),
            "consumption_kwh": 0.03,
        }
    ]
    with (
        patch(
            "homeassistant.components.wws.DynamiT.async_get_latest_prices",
            new_callable=AsyncMock,
            return_value=prices,
        ),
        patch(
            "homeassistant.components.wws.DynamiT.async_get_latest_measurements",
            new_callable=AsyncMock,
            return_value=measurements,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)

    await hass.async_block_till_done()

    assert hass.states.get("sensor.wws_price_ct_kwh").state == "0.35"
    assert hass.states.get("sensor.wws_next_price_ct_kwh").state == "0.35"
    assert hass.states.get("sensor.wws_consumption_kwh").state == "0.03"


async def test_price_rolls_over_at_quarter_hour(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the current and next prices roll over at a quarter-hour boundary."""
    freezer.move_to(datetime(2024, 1, 1, 12, 29, 59, tzinfo=UTC))
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="WestfalenWIND Ökostrom smart",
        data={"username": "test@example.com", "password": "test-password"},
        unique_id="test@example.com",
    )
    mock_entry.add_to_hass(hass)
    prices = [
        {
            "start": (start := datetime(2024, 1, 1, 12, minute, tzinfo=UTC)),
            "end": start + timedelta(minutes=15),
            "price_ct_kwh": value,
        }
        for minute, value in ((0, 35), (15, 35), (30, 34), (45, 34))
    ]
    with (
        patch(
            "homeassistant.components.wws.DynamiT.async_get_latest_prices",
            new_callable=AsyncMock,
            return_value=prices,
        ) as mock_get_latest_prices,
        patch(
            "homeassistant.components.wws.DynamiT.async_get_latest_measurements",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get_latest_measurements,
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.wws_price_ct_kwh").state == "0.35"
        assert hass.states.get("sensor.wws_next_price_ct_kwh").state == "0.34"

        freezer.move_to(datetime(2024, 1, 1, 12, 30, tzinfo=UTC))
        async_fire_time_changed(hass, datetime(2024, 1, 1, 12, 30, tzinfo=UTC))
        await hass.async_block_till_done()

    assert hass.states.get("sensor.wws_price_ct_kwh").state == "0.34"
    assert hass.states.get("sensor.wws_next_price_ct_kwh").state == "0.34"
    assert mock_get_latest_prices.await_count == 1
    assert mock_get_latest_measurements.await_count == 1
