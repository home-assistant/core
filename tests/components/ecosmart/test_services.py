"""Test the ecosmart service actions."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aioecosmart import (
    EcosmartAuthError,
    EcosmartConnectionError,
    EcosmartError,
    EcosmartRateLimitError,
    EcosmartUnknownPocError,
    IcpScope,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ecosmart.const import DOMAIN, FORECAST_HOURS
from homeassistant.components.ecosmart.services import ATTR_ICP, SERVICE_GET_FORECASTS
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration
from .conftest import TEST_ICP, TEST_POC, load_forecast, load_identity

OTHER_ICP = IcpScope(
    icp="0000123456AB125",
    poc="ISL0661",
    network="OTPO",
    price_category_code="RSUC",
)


async def _get_forecasts(
    hass: HomeAssistant, entry_id: str, **extra: str
) -> dict[str, object]:
    """Call the action and return its response."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_CONFIG_ENTRY_ID: entry_id, **extra},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    return response


async def test_get_forecasts(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the forecast for the key's only grid exit point is returned."""
    await setup_integration(hass, mock_config_entry)

    response = await _get_forecasts(hass, mock_config_entry.entry_id)

    assert response == snapshot
    mock_ecosmart_client.forecast.assert_awaited_once_with(TEST_POC, FORECAST_HOURS)


async def test_get_forecasts_leaves_the_spot_poll_alone(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the action makes one forecast request and no spot request."""
    await setup_integration(hass, mock_config_entry)
    mock_ecosmart_client.spot.reset_mock()

    await _get_forecasts(hass, mock_config_entry.entry_id)

    mock_ecosmart_client.spot.assert_not_awaited()
    mock_ecosmart_client.forecast.assert_awaited_once()


async def test_get_forecasts_empty(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an empty forecast is a valid answer that says why it is empty."""
    mock_ecosmart_client.forecast.return_value = load_forecast("forecast_empty.json")
    await setup_integration(hass, mock_config_entry)

    response = await _get_forecasts(hass, mock_config_entry.entry_id)

    assert response == {
        "published_at": None,
        "covered_hours": 0.0,
        "unavailable_reason": (
            "No WITS forecast is published for this grid exit point yet."
        ),
        "forecasts": [],
    }


async def test_get_forecasts_negative_price(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a negative wholesale price passes through with its sign."""
    forecast = load_forecast()
    negative = replace(
        forecast.points[0],
        price_cents_per_kwh=-6.64,
        price_cents_per_kwh_incl_gst=-7.636,
    )
    mock_ecosmart_client.forecast.return_value = replace(forecast, points=[negative])
    await setup_integration(hass, mock_config_entry)

    response = await _get_forecasts(hass, mock_config_entry.entry_id)

    assert response["forecasts"] == [
        {
            "start_time": "2026-08-24T15:00:00+00:00",
            "trading_date": "2026-08-25",
            "trading_period": 7,
            "schedule": "short",
            "price": -7.636,
            "price_excl_gst": -6.64,
        }
    ]


@pytest.mark.parametrize(
    ("error", "translation_key", "placeholders"),
    [
        (EcosmartAuthError("revoked", status=401), "invalid_auth", None),
        (
            EcosmartRateLimitError("slow down", status=429, retry_after=42),
            "forecast_rate_limited",
            {"retry_after": "42"},
        ),
        (
            EcosmartRateLimitError("slow down", status=429),
            "forecast_rate_limited",
            {"retry_after": "300"},
        ),
        (EcosmartConnectionError("timed out"), "cannot_connect", None),
        (EcosmartUnknownPocError("gone", status=404), "cannot_connect", None),
        (EcosmartError("contract moved"), "cannot_connect", None),
    ],
)
async def test_get_forecasts_api_errors(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: EcosmartError,
    translation_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Test an API failure is raised as a translated Home Assistant error."""
    await setup_integration(hass, mock_config_entry)
    mock_ecosmart_client.forecast.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await _get_forecasts(hass, mock_config_entry.entry_id)

    # An API failure is not the caller's mistake, so never a validation error.
    assert not isinstance(exc_info.value, ServiceValidationError)
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == placeholders


async def test_get_forecasts_entry_not_loaded(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the action refuses an entry that is not loaded."""
    await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_forecasts(hass, mock_config_entry.entry_id)

    assert exc_info.value.translation_key == "service_config_entry_not_loaded"
    mock_ecosmart_client.forecast.assert_not_awaited()


async def test_get_forecasts_unknown_entry(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the action refuses a config entry ID that does not exist."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_forecasts(hass, "not_a_real_entry")

    assert exc_info.value.translation_key == "service_config_entry_not_found"
    mock_ecosmart_client.forecast.assert_not_awaited()


async def test_get_forecasts_other_integration_entry(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the action refuses a config entry that belongs to another integration."""
    await setup_integration(hass, mock_config_entry)
    other_entry = MockConfigEntry(domain="other_domain")
    other_entry.add_to_hass(hass)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_forecasts(hass, other_entry.entry_id)

    assert exc_info.value.translation_key == "service_config_entry_wrong_domain"
    mock_ecosmart_client.forecast.assert_not_awaited()


async def test_get_forecasts_icp_on_shared_grid_exit_point(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test two ICPs behind one grid exit point need no ICP to be named."""
    identity = load_identity()
    second = replace(identity.allowed_icps[0], icp="0000123456AB124")
    mock_ecosmart_client.me.return_value = replace(
        identity, allowed_icps=[identity.allowed_icps[0], second]
    )
    await setup_integration(hass, mock_config_entry)

    await _get_forecasts(hass, mock_config_entry.entry_id)

    mock_ecosmart_client.forecast.assert_awaited_once_with(TEST_POC, FORECAST_HOURS)


async def test_get_forecasts_named_icp(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test naming an ICP fetches the forecast for its own grid exit point."""
    identity = load_identity()
    mock_ecosmart_client.me.return_value = replace(
        identity, allowed_icps=[identity.allowed_icps[0], OTHER_ICP]
    )
    await setup_integration(hass, mock_config_entry)

    await _get_forecasts(hass, mock_config_entry.entry_id, **{ATTR_ICP: OTHER_ICP.icp})

    mock_ecosmart_client.forecast.assert_awaited_once_with(
        OTHER_ICP.poc, FORECAST_HOURS
    )


async def test_get_forecasts_icp_required(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a key spanning two grid exit points needs the ICP named."""
    identity = load_identity()
    mock_ecosmart_client.me.return_value = replace(
        identity, allowed_icps=[identity.allowed_icps[0], OTHER_ICP]
    )
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_forecasts(hass, mock_config_entry.entry_id)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "icp_required"
    assert exc_info.value.translation_placeholders == {
        "icps": f"{TEST_ICP}, {OTHER_ICP.icp}"
    }
    mock_ecosmart_client.forecast.assert_not_awaited()


async def test_get_forecasts_icp_not_on_key(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test naming an ICP the key does not cover is refused before any request."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_forecasts(
            hass, mock_config_entry.entry_id, **{ATTR_ICP: "0000999999ZZ999"}
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "icp_not_found"
    assert exc_info.value.translation_placeholders == {
        "icp": "0000999999ZZ999",
        "icps": TEST_ICP,
    }
    mock_ecosmart_client.forecast.assert_not_awaited()


async def test_get_forecasts_key_without_icps(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a key that has lost its connection points is refused, not crashed."""
    mock_ecosmart_client.me.return_value = load_identity("me_no_icps.json")
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_forecasts(hass, mock_config_entry.entry_id)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "no_icps"
    mock_ecosmart_client.forecast.assert_not_awaited()
