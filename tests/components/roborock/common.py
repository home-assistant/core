"""Common methods used across tests for Roborock."""
from unittest.mock import patch

from homeassistant.components.roborock.const import (
    CAMERA,
    CONF_BASE_URL,
    CONF_BOTTOM,
    CONF_ENTRY_USERNAME,
    CONF_INCLUDE_SHARED,
    CONF_LEFT,
    CONF_MAP_TRANSFORM,
    CONF_RIGHT,
    CONF_ROTATE,
    CONF_SCALE,
    CONF_TOP,
    CONF_TRIM,
    CONF_USER_DATA,
    DOMAIN,
    VACUUM,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .mock_data import BASE_URL, HOME_DATA, HOME_DATA_SHARED, USER_DATA, USER_EMAIL

from tests.common import MockConfigEntry


async def setup_platform(
    hass: HomeAssistant, platform: str, include_shared: bool = True
) -> MockConfigEntry:
    """Set up the Roborock platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title=USER_EMAIL,
        data={
            CONF_ENTRY_USERNAME: USER_EMAIL,
            CONF_USER_DATA: USER_DATA,
            CONF_BASE_URL: BASE_URL,
        },
        options={
            CAMERA: {
                f"{CONF_MAP_TRANSFORM}.{CONF_SCALE}": 1.0,
                f"{CONF_MAP_TRANSFORM}.{CONF_ROTATE}": "90",
                f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_LEFT}": 5.0,
                f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_RIGHT}": 5.0,
                f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_TOP}": 5.0,
                f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_BOTTOM}": 5.0,
            },
            VACUUM: {
                CONF_INCLUDE_SHARED: include_shared,
            },
        },
    )
    mock_entry.add_to_hass(hass)

    home_data = HOME_DATA_SHARED if include_shared else HOME_DATA

    with patch("custom_components.roborock.PLATFORMS", [platform]), patch(
        "roborock.RoborockClient.get_home_data",
        return_value=home_data,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return mock_entry
