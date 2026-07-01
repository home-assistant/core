"""Test OpenAQ data coordinator helpers."""

from types import MappingProxyType
from typing import cast
from unittest.mock import MagicMock, patch

from openaq import NotAuthorizedError, OpenAQ, ServerError
import pytest

from homeassistant.components.openaq.const import (
    CONF_LOCATION_ID,
    DOMAIN,
    OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER,
    OPENAQ_UNIT_MILLIGRAMS_PER_CUBIC_METER,
)
from homeassistant.components.openaq.coordinator import (
    OpenAQDataUpdateCoordinator,
    OpenAQMeasurement,
    OpenAQSensorMetadata,
    async_create_openaq_client,
    create_openaq_client,
    normalize_latest_measurements,
    normalize_sensor_metadata,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import API_KEY, LOCATION_ID, make_latest, make_sensor

from tests.common import MockConfigEntry


def test_create_openaq_client_uses_sync_openaq_client() -> None:
    """Test creating an OpenAQ client uses the sync SDK client."""
    client = create_openaq_client("api-key")

    try:
        assert isinstance(client, OpenAQ)
        assert client.api_key == "api-key"
    finally:
        client.close()


async def test_async_create_openaq_client_uses_executor(
    hass: HomeAssistant,
) -> None:
    """Test creating an OpenAQ client through Home Assistant."""
    mock_client = MagicMock()

    with patch(
        "homeassistant.components.openaq.coordinator.create_openaq_client",
        return_value=mock_client,
    ) as mock_create:
        client = await async_create_openaq_client(hass, "api-key")

    assert client is mock_client
    mock_create.assert_called_once_with("api-key")


@pytest.mark.parametrize(
    ("first_exception", "expected_translation_key"),
    [
        (
            ServerError("API error"),
            "unable_to_fetch",
        ),
        (
            RuntimeError("Unexpected error"),
            "unable_to_fetch",
        ),
    ],
)
async def test_initial_refresh_exception_group_maps_error(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    first_exception: Exception,
    expected_translation_key: str,
) -> None:
    """Test initial refresh errors raise UpdateFailed."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenAQ",
        data={CONF_API_KEY: API_KEY},
        unique_id=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_LOCATION_ID: LOCATION_ID},
                subentry_id="ABCDEF",
                subentry_type="location",
                title="Del Norte",
                unique_id=str(LOCATION_ID),
            )
        ],
    )
    coordinator = OpenAQDataUpdateCoordinator(
        hass,
        config_entry,
        next(iter(config_entry.subentries.values())),
        mock_openaq_client,
    )
    mock_openaq_client.locations.get.side_effect = first_exception
    mock_openaq_client.locations.latest.side_effect = RuntimeError("Unexpected error")

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()

    assert err.value.__cause__ is first_exception
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == expected_translation_key


async def test_initial_refresh_auth_error_raises_config_entry_auth_failed(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
) -> None:
    """Test initial refresh auth errors raise ConfigEntryAuthFailed."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenAQ",
        data={CONF_API_KEY: API_KEY},
        unique_id=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_LOCATION_ID: LOCATION_ID},
                subentry_id="ABCDEF",
                subentry_type="location",
                title="Del Norte",
                unique_id=str(LOCATION_ID),
            )
        ],
    )
    coordinator = OpenAQDataUpdateCoordinator(
        hass,
        config_entry,
        next(iter(config_entry.subentries.values())),
        mock_openaq_client,
    )
    auth_error = NotAuthorizedError("Invalid API key")
    mock_openaq_client.locations.get.side_effect = auth_error

    with pytest.raises(ConfigEntryAuthFailed) as err:
        await coordinator._async_update_data()

    assert err.value.__cause__ is auth_error
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "authentication_failed"


async def test_initial_refresh_runs_sdk_calls_in_executor(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test blocking SDK calls run in the executor."""
    coordinator = OpenAQDataUpdateCoordinator(
        hass,
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        mock_openaq_client,
    )

    with patch.object(
        hass, "async_add_executor_job", wraps=hass.async_add_executor_job
    ) as mock_executor:
        await coordinator._async_update_data()

    assert [call.args[0] for call in mock_executor.call_args_list] == [
        mock_openaq_client.locations.get,
        mock_openaq_client.locations.latest,
        mock_openaq_client.locations.sensors,
    ]


def test_normalize_latest_measurements() -> None:
    """Test normalizing latest measurements by sensor metadata."""
    measurements = normalize_latest_measurements(
        [
            make_latest(1, 8.5),
            make_latest(999, 44.1),
            make_latest(2, None),
        ],
        [
            make_sensor(1, "pm2.5", "µg/m3"),
            make_sensor(2, "pm10"),
        ],
    )

    assert measurements == MappingProxyType(
        {
            "pm25": OpenAQMeasurement(
                parameter="pm25",
                value=8.5,
                unit=OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER,
            ),
        }
    )


def test_normalize_sensor_metadata() -> None:
    """Test normalizing sensor metadata by parameter."""
    metadata = normalize_sensor_metadata(
        [
            make_sensor(1, "pm2.5", "µg/m3"),
            make_sensor(2, "pm10"),
        ]
    )

    assert metadata == MappingProxyType(
        {
            "pm25": OpenAQSensorMetadata(
                parameter="pm25",
                unit=OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER,
            ),
            "pm10": OpenAQSensorMetadata(
                parameter="pm10",
                unit=OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER,
            ),
        }
    )


@pytest.mark.parametrize(
    ("unit", "expected_unit"),
    [
        ("μg/m³", OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER),
        ("mg/m³", OPENAQ_UNIT_MILLIGRAMS_PER_CUBIC_METER),
        ("mg/m3", OPENAQ_UNIT_MILLIGRAMS_PER_CUBIC_METER),
    ],
)
def test_normalize_latest_measurements_normalizes_unit_aliases(
    unit: str, expected_unit: str
) -> None:
    """Test normalizing measurement unit aliases."""
    measurements = normalize_latest_measurements(
        [make_latest(1, 12.1)],
        [make_sensor(1, "pm10", unit)],
    )

    assert measurements == MappingProxyType(
        {
            "pm10": OpenAQMeasurement(
                parameter="pm10",
                value=12.1,
                unit=expected_unit,
            )
        }
    )


def test_normalize_latest_measurements_allows_missing_units() -> None:
    """Test normalizing a measurement without a reported unit."""
    measurements = normalize_latest_measurements(
        [make_latest(1, 12.1)],
        [make_sensor(1, "pm10", cast(str, None))],
    )

    assert measurements == MappingProxyType(
        {
            "pm10": OpenAQMeasurement(
                parameter="pm10",
                value=12.1,
                unit=None,
            )
        }
    )


async def test_update_data_auth_error_raises_config_entry_auth_failed(
    hass: HomeAssistant,
    mock_openaq_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test refresh auth errors raise ConfigEntryAuthFailed."""
    coordinator = OpenAQDataUpdateCoordinator(
        hass,
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        mock_openaq_client,
    )
    await coordinator._async_update_data()
    mock_openaq_client.locations.latest.side_effect = NotAuthorizedError(
        "Invalid API key"
    )

    with pytest.raises(ConfigEntryAuthFailed) as err:
        await coordinator._async_update_data()

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "authentication_failed"
