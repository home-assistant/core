"""Test the Škoda services."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.skoda.const import DOMAIN
from homeassistant.components.skoda.services import SkodaService
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration


@pytest.mark.usefixtures("mock_skoda_client")
async def test_get_image_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the vehicle render URL is returned."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SkodaService.GET_IMAGE_URL,
        {CommonServiceArgument.CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response == {
        "url": "https://iprenders.blob.core.windows.net/base5azs22200218/enyaq_side1080.png"
    }


@pytest.mark.parametrize("vehicle_fixture", ["vehicle_hybrid.json"])
@pytest.mark.usefixtures("mock_skoda_client")
async def test_get_image_url_render_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an error is raised when the response has no render URL."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SkodaService.GET_IMAGE_URL,
            {CommonServiceArgument.CONFIG_ENTRY_ID: mock_config_entry.entry_id},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == "render_unavailable"


@pytest.mark.usefixtures("mock_skoda_client")
async def test_get_image_url_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an error is raised when the config entry is not loaded."""
    await setup_integration(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SkodaService.GET_IMAGE_URL,
            {CommonServiceArgument.CONFIG_ENTRY_ID: mock_config_entry.entry_id},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == "service_config_entry_not_loaded"
