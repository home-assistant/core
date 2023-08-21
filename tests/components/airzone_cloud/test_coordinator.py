"""Define tests for the Airzone Cloud coordinator."""

from unittest.mock import patch

from aioairzone_cloud.exceptions import AirzoneCloudError

from homeassistant.components.airzone_cloud.const import DOMAIN
from homeassistant.components.airzone_cloud.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .util import (
    CONFIG,
    GET_INSTALLATION_MOCK,
    GET_INSTALLATIONS_MOCK,
    mock_get_device_status,
    mock_get_webserver,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_client_connector_error(hass: HomeAssistant) -> None:
    """Test ClientConnectorError on coordinator update."""

    config_entry = MockConfigEntry(
        data=CONFIG,
        domain=DOMAIN,
        unique_id="airzone_cloud_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_get_device_status",
        side_effect=mock_get_device_status,
    ) as mock_device_status, patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_get_installation",
        return_value=GET_INSTALLATION_MOCK,
    ) as mock_installation, patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_get_installations",
        return_value=GET_INSTALLATIONS_MOCK,
    ) as mock_installations, patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_get_webserver",
        side_effect=mock_get_webserver,
    ) as mock_webserver, patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.login",
        return_value=None,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        mock_device_status.assert_called()
        mock_installation.assert_awaited_once()
        mock_installations.assert_called_once()
        mock_webserver.assert_called()

        mock_device_status.reset_mock()
        mock_installation.reset_mock()
        mock_installations.reset_mock()
        mock_webserver.reset_mock()

        mock_device_status.side_effect = AirzoneCloudError
        async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()

        mock_device_status.assert_called()

        state = hass.states.get("sensor.salon_temperature")
        assert state.state == STATE_UNAVAILABLE
