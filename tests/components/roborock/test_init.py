"""Test for Roborock init."""

from copy import deepcopy
from http import HTTPStatus
import pathlib
from typing import Any
from unittest.mock import patch

import pytest
from roborock import (
    RoborockException,
    RoborockInvalidCredentials,
    RoborockInvalidUserAgreement,
    RoborockNoUserAgreement,
)

from homeassistant.components.roborock.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.setup import async_setup_component

from .mock_data import (
    HOME_DATA,
    NETWORK_INFO,
    NETWORK_INFO_2,
    ROBOROCK_RRUID,
    USER_EMAIL,
)

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_unload_entry(
    hass: HomeAssistant, bypass_api_fixture, setup_entry: MockConfigEntry
) -> None:
    """Test unloading roboorck integration."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert setup_entry.state is ConfigEntryState.LOADED
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.async_release"
    ) as mock_disconnect:
        assert await hass.config_entries.async_unload(setup_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_disconnect.call_count == 2
        assert setup_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test that when coordinator update fails, entry retries."""
    with (
        patch(
            "homeassistant.components.roborock.RoborockApiClient.get_home_data_v3",
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            side_effect=RoborockException(),
        ),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_not_ready_home_data(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test that when we fail to get home data, entry retries."""
    with (
        patch(
            "homeassistant.components.roborock.RoborockApiClient.get_home_data_v3",
            side_effect=RoborockException(),
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            side_effect=RoborockException(),
        ),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_networking_fails(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture_v1_only,
) -> None:
    """Test that when networking fails, we attempt to retry."""
    with patch(
        "homeassistant.components.roborock.RoborockMqttClientV1.get_networking",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_networking_fails_none(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture_v1_only,
) -> None:
    """Test that when networking returns None, we attempt to retry."""
    with patch(
        "homeassistant.components.roborock.RoborockMqttClientV1.get_networking",
        return_value=None,
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_cloud_client_fails_props(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture_v1_only,
) -> None:
    """Test that if networking succeeds, but we can't communicate with the vacuum, we can't get props, fail."""
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.ping",
            side_effect=RoborockException(),
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMqttClientV1.get_prop",
            side_effect=RoborockException(),
        ),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_local_client_fails_props(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture_v1_only,
) -> None:
    """Test that if networking succeeds, but we can't communicate locally with the vacuum, we can't get props, fail."""
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_fail_maps(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture_v1_only,
) -> None:
    """Test that the integration fails to load if we fail to get the maps."""
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_multi_maps_list",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_reauth_started(
    hass: HomeAssistant, bypass_api_fixture, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test reauth flow started."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data_v3",
        side_effect=RoborockInvalidCredentials(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize("platforms", [[Platform.IMAGE]])
async def test_remove_from_hass(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    storage_path: pathlib.Path,
) -> None:
    """Test that removing from hass removes any existing images."""

    # Ensure some image content is cached
    assert hass.states.get("image.roborock_s7_maxv_upstairs") is not None
    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    assert resp.status == HTTPStatus.OK

    config_entry_storage = storage_path / setup_entry.entry_id
    assert not config_entry_storage.exists()

    # Flush to disk
    await hass.config_entries.async_unload(setup_entry.entry_id)
    assert config_entry_storage.exists()
    paths = list(config_entry_storage.walk())
    assert len(paths) == 4  # Two map image and two directories

    await hass.config_entries.async_remove(setup_entry.entry_id)
    # After removal, directories should be empty.
    assert not config_entry_storage.exists()


@pytest.mark.parametrize("platforms", [[Platform.IMAGE]])
async def test_oserror_remove_image(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    storage_path: pathlib.Path,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we gracefully handle failing to remove an image."""

    # Ensure some image content is cached
    assert hass.states.get("image.roborock_s7_maxv_upstairs") is not None
    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    assert resp.status == HTTPStatus.OK

    # Image content is saved when unloading
    config_entry_storage = storage_path / setup_entry.entry_id
    assert not config_entry_storage.exists()
    await hass.config_entries.async_unload(setup_entry.entry_id)

    assert config_entry_storage.exists()
    paths = list(config_entry_storage.walk())
    assert len(paths) == 4  # Two map image and two directories

    with patch(
        "homeassistant.components.roborock.roborock_storage.shutil.rmtree",
        side_effect=OSError,
    ):
        await hass.config_entries.async_remove(setup_entry.entry_id)
    assert "Unable to remove map files" in caplog.text


async def test_not_supported_protocol(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we output a message on incorrect protocol."""
    home_data_copy = deepcopy(HOME_DATA)
    home_data_copy.received_devices[0].pv = "random"
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data_v3",
        return_value=home_data_copy,
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()
    assert "because its protocol version random" in caplog.text


async def test_not_supported_a01_device(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we output a message on incorrect category."""
    home_data_copy = deepcopy(HOME_DATA)
    home_data_copy.products[2].category = "random"
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data_v3",
        return_value=home_data_copy,
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
    assert "The device you added is not yet supported" in caplog.text


async def test_invalid_user_agreement(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test that we fail setting up if the user agreement is out of date."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data_v3",
        side_effect=RoborockInvalidUserAgreement(),
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY
        assert (
            mock_roborock_entry.error_reason_translation_key == "invalid_user_agreement"
        )


async def test_no_user_agreement(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test that we fail setting up if the user has no agreement."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data_v3",
        side_effect=RoborockNoUserAgreement(),
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY
        assert mock_roborock_entry.error_reason_translation_key == "no_user_agreement"


@pytest.mark.parametrize("platforms", [[Platform.SENSOR]])
async def test_stale_device(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test that we remove a device if it no longer is given by home_data."""
    with patch(
        "homeassistant.components.roborock.RoborockMqttClientV1.get_networking",
        side_effect=[NETWORK_INFO, NETWORK_INFO_2],
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    assert mock_roborock_entry.state is ConfigEntryState.LOADED
    existing_devices = device_registry.devices.get_devices_for_config_entry_id(
        mock_roborock_entry.entry_id
    )
    assert len(existing_devices) == 6  # 2 for each robot, 1 for A01, 1 for Zeo
    hd = deepcopy(HOME_DATA)
    hd.devices = [hd.devices[0]]

    with (
        patch(
            "homeassistant.components.roborock.RoborockApiClient.get_home_data_v3",
            return_value=hd,
        ),
        patch(
            "homeassistant.components.roborock.RoborockMqttClientV1.get_networking",
            side_effect=[NETWORK_INFO, NETWORK_INFO_2],
        ),
    ):
        await hass.config_entries.async_reload(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()
    new_devices = device_registry.devices.get_devices_for_config_entry_id(
        mock_roborock_entry.entry_id
    )
    assert (
        len(new_devices) == 4
    )  # 2 for the one remaining robot. 1 for both the A01s which are shared and
    # therefore not deleted.


@pytest.mark.parametrize("platforms", [[Platform.SENSOR]])
async def test_no_stale_device(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test that we don't remove a device if fails to setup."""
    with patch(
        "homeassistant.components.roborock.RoborockMqttClientV1.get_networking",
        side_effect=[NETWORK_INFO, NETWORK_INFO_2],
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    assert mock_roborock_entry.state is ConfigEntryState.LOADED
    existing_devices = device_registry.devices.get_devices_for_config_entry_id(
        mock_roborock_entry.entry_id
    )
    assert len(existing_devices) == 6  # 2 for each robot, 1 for A01, 1 for Zeo

    with patch(
        "homeassistant.components.roborock.RoborockMqttClientV1.get_networking",
        side_effect=[NETWORK_INFO, RoborockException],
    ):
        await hass.config_entries.async_reload(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()
    new_devices = device_registry.devices.get_devices_for_config_entry_id(
        mock_roborock_entry.entry_id
    )
    assert len(new_devices) == 6  # 2 for each robot, 1 for A01, 1 for Zeo


async def test_migrate_config_entry_unique_id(
    hass: HomeAssistant,
    bypass_api_fixture,
    config_entry_data: dict[str, Any],
) -> None:
    """Test migrating the config entry unique id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_EMAIL,
        data=config_entry_data,
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.unique_id == ROBOROCK_RRUID
