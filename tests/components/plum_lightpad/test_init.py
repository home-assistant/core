"""Tests for the Plum Lightpad config flow."""
from aiohttp import ContentTypeError
from requests.exceptions import HTTPError

from homeassistant.components.plum_lightpad.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.async_mock import Mock, patch
from tests.common import MockConfigEntry


async def test_async_setup_no_domain_config(hass: HomeAssistant):
    """Test setup without configuration is noop."""
    result = await async_setup_component(hass, DOMAIN, {})

    assert result is True
    assert DOMAIN not in hass.data


async def test_async_setup_imports_from_config(hass: HomeAssistant):
    """Test that specifying config will setup an entry."""
    with patch(
        "homeassistant.components.plum_lightpad.utils.Plum.loadCloudData"
    ) as mock_loadCloudData, patch(
        "homeassistant.components.plum_lightpad.async_setup_entry", return_value=True,
    ) as mock_async_setup_entry:
        result = await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    "username": "test-plum-username",
                    "password": "test-plum-password",
                }
            },
        )
        await hass.async_block_till_done()

    assert result is True
    assert len(mock_loadCloudData.mock_calls) == 1
    assert len(mock_async_setup_entry.mock_calls) == 1


async def test_async_setup_entry_sets_up_light(hass: HomeAssistant):
    """Test that configuring entry sets up light domain."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-plum-username", "password": "test-plum-password"},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.plum_lightpad.utils.Plum.loadCloudData"
    ) as mock_loadCloudData, patch(
        "homeassistant.components.plum_lightpad.light.async_setup_entry"
    ) as mock_light_async_setup_entry:
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        assert result is True

        await hass.async_block_till_done()

    assert len(mock_loadCloudData.mock_calls) == 1
    assert len(mock_light_async_setup_entry.mock_calls) == 1


async def test_async_setup_entry_handles_auth_error(hass: HomeAssistant):
    """Test that configuring entry handles Plum Cloud authentication error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-plum-username", "password": "test-plum-password"},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.plum_lightpad.utils.Plum.loadCloudData",
        side_effect=ContentTypeError(Mock(), None),
    ), patch(
        "homeassistant.components.plum_lightpad.light.async_setup_entry"
    ) as mock_light_async_setup_entry:
        result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is False
    assert len(mock_light_async_setup_entry.mock_calls) == 0


async def test_async_setup_entry_handles_http_error(hass: HomeAssistant):
    """Test that configuring entry handles HTTP error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-plum-username", "password": "test-plum-password"},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.plum_lightpad.utils.Plum.loadCloudData",
        side_effect=HTTPError,
    ), patch(
        "homeassistant.components.plum_lightpad.light.async_setup_entry"
    ) as mock_light_async_setup_entry:
        result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is False
    assert len(mock_light_async_setup_entry.mock_calls) == 0
