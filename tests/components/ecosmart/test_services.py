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
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ecosmart.const import DOMAIN, FORECAST_HOURS
from homeassistant.components.ecosmart.services import EcosmartService
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import TEST_ICP, TEST_POC, load_forecast, load_identity

OTHER_ICP = IcpScope(
    icp="0000123456AB125",
    poc="ISL0661",
    network="OTPO",
    price_category_code="RSUC",
)


def _device_id(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry, icp: str = TEST_ICP
) -> str:
    """Return the ID of the device ecosmart created for an ICP."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, icp), entry.entry_id
    )
    assert device is not None
    return device.id


async def _get_forecasts(hass: HomeAssistant, device_id: str) -> dict[str, object]:
    """Call the action and return its response."""
    response = await hass.services.async_call(
        DOMAIN,
        EcosmartService.GET_FORECASTS,
        {ATTR_DEVICE_ID: device_id},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    return response


async def test_get_forecasts(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the forecast for the chosen connection point is returned."""
    await setup_integration(hass, mock_config_entry)

    response = await _get_forecasts(
        hass, _device_id(device_registry, mock_config_entry)
    )

    assert response == snapshot
    mock_ecosmart_client.forecast.assert_awaited_once_with(TEST_POC, FORECAST_HOURS)


async def test_get_forecasts_leaves_the_spot_poll_alone(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the action makes one forecast request and no spot request."""
    await setup_integration(hass, mock_config_entry)
    mock_ecosmart_client.spot.reset_mock()

    await _get_forecasts(hass, _device_id(device_registry, mock_config_entry))

    mock_ecosmart_client.spot.assert_not_awaited()
    mock_ecosmart_client.forecast.assert_awaited_once()


async def test_get_forecasts_empty(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test an empty forecast is a valid answer, not an error."""
    mock_ecosmart_client.forecast.return_value = load_forecast("forecast_empty.json")
    await setup_integration(hass, mock_config_entry)

    response = await _get_forecasts(
        hass, _device_id(device_registry, mock_config_entry)
    )

    assert response == {"forecasts": []}


async def test_get_forecasts_negative_price(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
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

    response = await _get_forecasts(
        hass, _device_id(device_registry, mock_config_entry)
    )

    assert response["forecasts"] == [
        {
            "start_time": "2026-08-24T15:00:00+00:00",
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
    device_registry: dr.DeviceRegistry,
    error: EcosmartError,
    translation_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Test an API failure is raised as a translated Home Assistant error."""
    await setup_integration(hass, mock_config_entry)
    mock_ecosmart_client.forecast.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await _get_forecasts(hass, _device_id(device_registry, mock_config_entry))

    # An API failure is not the caller's mistake, so never a validation error.
    assert not isinstance(exc_info.value, ServiceValidationError)
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == placeholders


async def test_get_forecasts_second_grid_exit_point(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test each connection point fetches the forecast for its own grid exit point."""
    identity = load_identity()
    mock_ecosmart_client.me.return_value = replace(
        identity, allowed_icps=[identity.allowed_icps[0], OTHER_ICP]
    )
    await setup_integration(hass, mock_config_entry)

    await _get_forecasts(
        hass, _device_id(device_registry, mock_config_entry, OTHER_ICP.icp)
    )
    mock_ecosmart_client.forecast.assert_awaited_once_with(
        OTHER_ICP.poc, FORECAST_HOURS
    )

    mock_ecosmart_client.forecast.reset_mock()
    await _get_forecasts(hass, _device_id(device_registry, mock_config_entry))
    mock_ecosmart_client.forecast.assert_awaited_once_with(TEST_POC, FORECAST_HOURS)


async def test_get_forecasts_requires_a_device(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the connection point must be chosen; nothing is picked by default."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            EcosmartService.GET_FORECASTS,
            {},
            blocking=True,
            return_response=True,
        )

    mock_ecosmart_client.forecast.assert_not_awaited()


async def test_get_forecasts_unknown_device(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the action refuses a device ID that does not exist."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_forecasts(hass, "not_a_real_device")

    assert exc_info.value.translation_key == "service_device_not_found"
    mock_ecosmart_client.forecast.assert_not_awaited()


async def test_get_forecasts_other_integration_device(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the action refuses a device that belongs to another integration."""
    await setup_integration(hass, mock_config_entry)
    other_entry = MockConfigEntry(domain="other_domain")
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other_domain", TEST_ICP)},
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_forecasts(hass, other_device.id)

    assert exc_info.value.translation_key == "service_device_wrong_domain"
    mock_ecosmart_client.forecast.assert_not_awaited()


async def test_get_forecasts_entry_not_loaded(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the action refuses a device whose config entry is not loaded."""
    await setup_integration(hass, mock_config_entry)
    device_id = _device_id(device_registry, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_forecasts(hass, device_id)

    assert exc_info.value.translation_key == "service_config_entry_not_loaded"
    mock_ecosmart_client.forecast.assert_not_awaited()


async def test_get_forecasts_icp_no_longer_on_key(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device left behind by an ICP the key no longer covers is refused."""
    identity = load_identity()
    mock_ecosmart_client.me.return_value = replace(
        identity, allowed_icps=[identity.allowed_icps[0], OTHER_ICP]
    )
    await setup_integration(hass, mock_config_entry)
    stale_device_id = _device_id(device_registry, mock_config_entry, OTHER_ICP.icp)

    mock_ecosmart_client.me.return_value = identity
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_forecasts(hass, stale_device_id)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "icp_not_on_key"
    assert exc_info.value.translation_placeholders == {"icp": OTHER_ICP.icp}
    mock_ecosmart_client.forecast.assert_not_awaited()


async def test_get_forecasts_device_without_icp(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test an ecosmart device that names no ICP is refused before any request."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("other_domain", TEST_ICP)},
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await _get_forecasts(hass, device.id)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_device"
    assert exc_info.value.translation_placeholders == {"device_id": device.id}
    mock_ecosmart_client.forecast.assert_not_awaited()
