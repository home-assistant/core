"""Test the initialization of fujitsu_fglair entities."""

from unittest.mock import AsyncMock, patch

from ayla_iot_unofficial import AylaAuthError
from ayla_iot_unofficial.fujitsu_consts import FGLAIR_APP_CREDENTIALS
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.fujitsu_fglair.const import (
    API_REFRESH,
    API_TIMEOUT,
    CONF_EUROPE,
    CONF_REGION,
    DOMAIN,
    REGION_DEFAULT,
    REGION_EU,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, entity_registry as er

from . import entity_id, setup_integration
from .conftest import TEST_PASSWORD, TEST_USERNAME

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_auth_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[AsyncMock],
) -> None:
    """Test entities become unavailable after auth failure."""
    await setup_integration(hass, mock_config_entry)

    mock_ayla_api.async_get_devices.side_effect = AylaAuthError
    freezer.tick(API_REFRESH)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id(mock_devices[0])).state == STATE_UNAVAILABLE
    assert hass.states.get(entity_id(mock_devices[1])).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "mock_config_entry", FGLAIR_APP_CREDENTIALS.keys(), indirect=True
)
async def test_auth_regions(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[AsyncMock],
) -> None:
    """Test that we use the correct credentials if europe is selected."""
    with patch(
        "homeassistant.components.fujitsu_fglair.new_ayla_api", return_value=AsyncMock()
    ) as new_ayla_api_patch:
        await setup_integration(hass, mock_config_entry)
        new_ayla_api_patch.assert_called_once_with(
            TEST_USERNAME,
            TEST_PASSWORD,
            FGLAIR_APP_CREDENTIALS[mock_config_entry.data[CONF_REGION]][0],
            FGLAIR_APP_CREDENTIALS[mock_config_entry.data[CONF_REGION]][1],
            europe=mock_config_entry.data[CONF_REGION] == "EU",
            websession=aiohttp_client.async_get_clientsession(hass),
            timeout=API_TIMEOUT,
        )


@pytest.mark.parametrize("is_europe", [True, False])
async def test_migrate_entry_v11_v12(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_ayla_api: AsyncMock,
    is_europe: bool,
    mock_devices: list[AsyncMock],
) -> None:
    """Test migration from schema 1.1 to 1.2."""
    v11_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME,
        data={
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_EUROPE: is_europe,
        },
    )

    await setup_integration(hass, v11_config_entry)
    updated_entry = hass.config_entries.async_get_entry(v11_config_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.version == 1
    assert updated_entry.minor_version == 2
    if is_europe:
        assert updated_entry.data[CONF_REGION] is REGION_EU
    else:
        assert updated_entry.data[CONF_REGION] is REGION_DEFAULT


async def test_device_auth_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[AsyncMock],
) -> None:
    """Test entities become unavailable after auth failure with updating devices."""
    await setup_integration(hass, mock_config_entry)

    for d in mock_ayla_api.async_get_devices.return_value:
        d.async_update.side_effect = AylaAuthError

    freezer.tick(API_REFRESH)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id(mock_devices[0])).state == STATE_UNAVAILABLE
    assert hass.states.get(entity_id(mock_devices[1])).state == STATE_UNAVAILABLE


async def test_token_expired(
    hass: HomeAssistant,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Make sure sign_in is called if the token expired."""
    mock_ayla_api.token_expired = True
    await setup_integration(hass, mock_config_entry)

    # Called once during setup and once during update
    assert mock_ayla_api.async_sign_in.call_count == 2


async def test_token_expiring_soon(
    hass: HomeAssistant,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Make sure sign_in is called if the token expired."""
    mock_ayla_api.token_expiring_soon = True
    await setup_integration(hass, mock_config_entry)

    mock_ayla_api.async_refresh_auth.assert_called_once()


@pytest.mark.parametrize("exception", [AylaAuthError, TimeoutError])
async def test_startup_exception(
    hass: HomeAssistant,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Make sure that no devices are added if there was an exception while logging in."""
    mock_ayla_api.async_sign_in.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    assert len(hass.states.async_all()) == 0


async def test_one_device_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that coordinator only updates devices that are currently listening."""
    await setup_integration(hass, mock_config_entry)

    for d in mock_devices:
        d.async_update.assert_called_once()
        d.reset_mock()

    entity = entity_registry.async_get(
        entity_registry.async_get_entity_id(
            Platform.CLIMATE, DOMAIN, mock_devices[0].device_serial_number
        )
    )
    entity_registry.async_update_entity(
        entity.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    freezer.tick(API_REFRESH)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == len(mock_devices) - 1
    mock_devices[0].async_update.assert_not_called()
    mock_devices[1].async_update.assert_called_once()
