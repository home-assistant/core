"""Test core config."""

from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import config
from homeassistant.components.config import core
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, location
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockUser
from tests.typing import (
    ClientSessionGenerator,
    MockHAClientWebSocket,
    WebSocketGenerator,
)


@pytest.fixture
async def client(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """Fixture that can interact with the config manager API."""
    with patch.object(config, "SECTIONS", [core]):
        assert await async_setup_component(hass, "config", {})
    return await hass_ws_client(hass)


async def test_validate_config_ok(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test checking config."""
    with patch.object(config, "SECTIONS", [core]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    no_error = Mock()
    no_error.errors = None
    no_error.error_str = ""
    no_error.warning_str = ""

    with patch(
        "homeassistant.components.config.core.check_config.async_check_ha_config_file",
        return_value=no_error,
    ):
        resp = await client.post("/api/config/core/check_config")

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result["result"] == "valid"
    assert result["errors"] is None
    assert result["warnings"] is None

    error_warning = Mock()
    error_warning.errors = ["beer"]
    error_warning.error_str = "beer"
    error_warning.warning_str = "milk"

    with patch(
        "homeassistant.components.config.core.check_config.async_check_ha_config_file",
        return_value=error_warning,
    ):
        resp = await client.post("/api/config/core/check_config")

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result["result"] == "invalid"
    assert result["errors"] == "beer"
    assert result["warnings"] == "milk"

    warning = Mock()
    warning.errors = None
    warning.error_str = ""
    warning.warning_str = "milk"

    with patch(
        "homeassistant.components.config.core.check_config.async_check_ha_config_file",
        return_value=warning,
    ):
        resp = await client.post("/api/config/core/check_config")

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result["result"] == "valid"
    assert result["errors"] is None
    assert result["warnings"] == "milk"


async def test_validate_config_requires_admin(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test checking configuration does not work as a normal user."""
    with patch.object(config, "SECTIONS", [core]):
        await async_setup_component(hass, "config", {})

    client = await hass_client(hass_read_only_access_token)
    resp = await client.post("/api/config/core/check_config")

    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_websocket_core_update(hass: HomeAssistant, client) -> None:
    """Test core config update websocket command."""
    assert hass.config.latitude != 60
    assert hass.config.longitude != 50
    assert hass.config.elevation != 25
    assert hass.config.location_name != "Huis"
    assert hass.config.units is not US_CUSTOMARY_SYSTEM
    assert hass.config.time_zone != "America/New_York"
    assert hass.config.external_url != "https://www.example.com"
    assert hass.config.internal_url != "http://example.com"
    assert hass.config.currency == "EUR"
    assert hass.config.country != "SE"
    assert hass.config.language != "sv"
    assert hass.config.radius != 150

    with (
        patch("homeassistant.util.dt.set_default_time_zone") as mock_set_tz,
        patch(
            "homeassistant.components.config.core.async_update_suggested_units"
        ) as mock_update_sensor_units,
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "config/core/update",
                "latitude": 60,
                "longitude": 50,
                "elevation": 25,
                "location_name": "Huis",
                "unit_system": "imperial",
                "time_zone": "America/New_York",
                "external_url": "https://www.example.com",
                "internal_url": "http://example.local",
                "currency": "USD",
                "country": "SE",
                "language": "sv",
                "radius": 150,
            }
        )

        msg = await client.receive_json()

        mock_update_sensor_units.assert_not_called()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert hass.config.latitude == 60
    assert hass.config.longitude == 50
    assert hass.config.elevation == 25
    assert hass.config.location_name == "Huis"
    assert hass.config.units is US_CUSTOMARY_SYSTEM
    assert hass.config.external_url == "https://www.example.com"
    assert hass.config.internal_url == "http://example.local"
    assert hass.config.currency == "USD"
    assert hass.config.country == "SE"
    assert hass.config.language == "sv"
    assert hass.config.radius == 150

    assert len(mock_set_tz.mock_calls) == 1
    assert mock_set_tz.mock_calls[0][1][0] == dt_util.get_time_zone("America/New_York")

    with (
        patch("homeassistant.util.dt.set_default_time_zone") as mock_set_tz,
        patch(
            "homeassistant.components.config.core.async_update_suggested_units"
        ) as mock_update_sensor_units,
    ):
        await client.send_json(
            {
                "id": 6,
                "type": "config/core/update",
                "unit_system": "metric",
                "update_units": True,
            }
        )

        msg = await client.receive_json()

        mock_update_sensor_units.assert_called_once()


async def test_websocket_core_update_not_admin(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test core config fails for non admin."""
    hass_admin_user.groups = []
    with patch.object(config, "SECTIONS", [core]):
        await async_setup_component(hass, "config", {})

    client = await hass_ws_client(hass)
    await client.send_json({"id": 6, "type": "config/core/update", "latitude": 23})

    msg = await client.receive_json()

    assert msg["id"] == 6
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


async def test_websocket_bad_core_update(hass: HomeAssistant, client) -> None:
    """Test core config update fails with bad parameters."""
    await client.send_json({"id": 7, "type": "config/core/update", "latituude": 23})

    msg = await client.receive_json()

    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"


async def test_detect_config(hass: HomeAssistant, client) -> None:
    """Test detect config."""
    with patch(
        "homeassistant.util.location.async_detect_location_info",
        return_value=None,
    ):
        await client.send_json({"id": 1, "type": "config/core/detect"})

        msg = await client.receive_json()

    assert msg["success"] is True
    assert msg["result"] == {}


async def test_detect_config_fail(hass: HomeAssistant, client) -> None:
    """Test detect config."""
    with patch(
        "homeassistant.util.location.async_detect_location_info",
        return_value=location.LocationInfo(
            ip=None,
            country_code=None,
            currency=None,
            region_code=None,
            region_name=None,
            city=None,
            zip_code=None,
            latitude=None,
            longitude=None,
            use_metric=True,
            time_zone="Europe/Amsterdam",
        ),
    ):
        await client.send_json({"id": 1, "type": "config/core/detect"})

        msg = await client.receive_json()

    assert msg["success"] is True
    assert msg["result"] == {"unit_system": "metric", "time_zone": "Europe/Amsterdam"}
