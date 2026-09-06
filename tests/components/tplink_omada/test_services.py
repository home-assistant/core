"""Tests for TP-Link Omada integration services."""

from unittest.mock import MagicMock

import pytest
from tplink_omada_client import OmadaClientSettings
from tplink_omada_client.exceptions import OmadaClientException
import voluptuous as vol

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.services import async_setup_services
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_service_reconnect_no_config_entries(
    hass: HomeAssistant,
) -> None:
    """Test reconnect service raises error when no config entries exist."""
    # Register services directly without any config entries
    async_setup_services(hass)

    mac = "AA:BB:CC:DD:EE:FF"
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "reconnect_client",
            {"mac": mac},
            blocking=True,
        )
    assert err.value.translation_key == "no_controllers"
    assert err.value.translation_domain == DOMAIN


async def test_service_reconnect_client(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconnect client service."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "AA:BB:CC:DD:EE:FF"
    await hass.services.async_call(
        DOMAIN,
        "reconnect_client",
        {"config_entry_id": mock_config_entry.entry_id, "mac": mac},
        blocking=True,
    )

    mock_omada_site_client.reconnect_client.assert_awaited_once_with(mac)


async def test_service_reconnect_failed_with_invalid_entry(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconnect with invalid config entry raises ServiceValidationError."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "AA:BB:CC:DD:EE:FF"
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "reconnect_client",
            {"config_entry_id": "invalid_entry_id", "mac": mac},
            blocking=True,
        )
    assert err.value.translation_key == "controller_not_found"
    assert err.value.translation_domain == DOMAIN


async def test_service_reconnect_without_config_entry_id(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconnect client service without config_entry_id uses first loaded entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "AA:BB:CC:DD:EE:FF"
    await hass.services.async_call(
        DOMAIN,
        "reconnect_client",
        {"mac": mac},
        blocking=True,
    )

    mock_omada_site_client.reconnect_client.assert_awaited_once_with(mac)


async def test_service_reconnect_entry_not_loaded(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconnect service raises error when entry is not loaded."""
    # Set up first entry so service is registered
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unloaded_entry = MockConfigEntry(
        title="Unloaded Omada Controller",
        domain=DOMAIN,
        unique_id="67890",
    )
    unloaded_entry.add_to_hass(hass)

    mac = "AA:BB:CC:DD:EE:FF"
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "reconnect_client",
            {"config_entry_id": unloaded_entry.entry_id, "mac": mac},
            blocking=True,
        )
    assert err.value.translation_key == "controller_unavailable"
    assert err.value.translation_domain == DOMAIN


async def test_service_reconnect_failed_raises_homeassistanterror(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconnect client service raises correct exception on failure."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "AA:BB:CC:DD:EE:FF"
    mock_omada_site_client.reconnect_client.side_effect = OmadaClientException
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "reconnect_client",
            {"config_entry_id": mock_config_entry.entry_id, "mac": mac},
            blocking=True,
        )
    assert err.value.translation_key == "reconnect_failed"
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_placeholders == {"mac": mac}

    mock_omada_site_client.reconnect_client.assert_awaited_once_with(mac)


def _add_client_device(
    hass: HomeAssistant, config_entry: MockConfigEntry, mac: str
) -> str:
    """Register a device with a network MAC connection for the given entry."""
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
    )
    return device.id


def _add_device_without_mac(hass: HomeAssistant, config_entry: MockConfigEntry) -> str:
    """Register a device without a network MAC connection for the given entry."""
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "no-mac-device")},
    )
    return device.id


async def test_service_set_client_name_no_config_entries(
    hass: HomeAssistant,
) -> None:
    """Test set client name service raises error when no config entries exist."""
    async_setup_services(hass)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_client_name",
            {"device_id": "device1", "name": "Ting sensor"},
            blocking=True,
        )
    assert err.value.translation_key == "no_controllers"
    assert err.value.translation_domain == DOMAIN


async def test_service_set_client_name(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the name of a client."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "aa:bb:cc:dd:ee:ff"
    device_id = _add_client_device(hass, mock_config_entry, mac)

    await hass.services.async_call(
        DOMAIN,
        "set_client_name",
        {
            "config_entry_id": mock_config_entry.entry_id,
            "device_id": device_id,
            "name": "Ting sensor",
        },
        blocking=True,
    )

    mock_omada_site_client.update_client.assert_awaited_once_with(
        mac, OmadaClientSettings(name="Ting sensor")
    )


async def test_service_set_client_name_without_config_entry_id(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set client name without config_entry_id uses first loaded entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "aa:bb:cc:dd:ee:ff"
    device_id = _add_client_device(hass, mock_config_entry, mac)

    await hass.services.async_call(
        DOMAIN,
        "set_client_name",
        {"device_id": device_id, "name": "Ting sensor"},
        blocking=True,
    )

    mock_omada_site_client.update_client.assert_awaited_once_with(
        mac, OmadaClientSettings(name="Ting sensor")
    )


async def test_service_set_client_name_invalid_config_entry_id(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set client name with invalid config entry raises ServiceValidationError."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_client_name",
            {
                "config_entry_id": "invalid_entry_id",
                "device_id": "device1",
                "name": "Ting sensor",
            },
            blocking=True,
        )
    assert err.value.translation_key == "controller_not_found"
    assert err.value.translation_domain == DOMAIN


async def test_service_set_client_name_entry_not_loaded(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set client name raises error when entry is not loaded."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unloaded_entry = MockConfigEntry(
        title="Unloaded Omada Controller",
        domain=DOMAIN,
        unique_id="67890",
    )
    unloaded_entry.add_to_hass(hass)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_client_name",
            {
                "config_entry_id": unloaded_entry.entry_id,
                "device_id": "device1",
                "name": "Ting sensor",
            },
            blocking=True,
        )
    assert err.value.translation_key == "controller_unavailable"
    assert err.value.translation_domain == DOMAIN


async def test_service_set_client_name_unknown_device(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set client name with an unknown device raises ServiceValidationError."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_client_name",
            {"device_id": "nonexistent_device", "name": "Ting sensor"},
            blocking=True,
        )
    assert err.value.translation_key == "client_device_not_found"
    assert err.value.translation_domain == DOMAIN


async def test_service_set_client_name_device_without_mac(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set client name with a device without a MAC raises ServiceValidationError."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_id = _add_device_without_mac(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_client_name",
            {"device_id": device_id, "name": "Ting sensor"},
            blocking=True,
        )
    assert err.value.translation_key == "client_device_no_mac"
    assert err.value.translation_domain == DOMAIN


async def test_service_set_client_name_failed_raises_homeassistanterror(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set client name raises correct exception on controller failure."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "aa:bb:cc:dd:ee:ff"
    device_id = _add_client_device(hass, mock_config_entry, mac)

    mock_omada_site_client.update_client.side_effect = OmadaClientException
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_client_name",
            {"device_id": device_id, "name": "Ting sensor"},
            blocking=True,
        )
    assert err.value.translation_key == "set_client_name_failed"
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_placeholders == {"mac": mac}

    mock_omada_site_client.update_client.assert_awaited_once_with(
        mac, OmadaClientSettings(name="Ting sensor")
    )


async def test_service_set_client_name_empty_name_rejected(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set client name with an empty name is rejected by the schema."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "aa:bb:cc:dd:ee:ff"
    device_id = _add_client_device(hass, mock_config_entry, mac)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "set_client_name",
            {"device_id": device_id, "name": ""},
            blocking=True,
        )

    mock_omada_site_client.update_client.assert_not_awaited()
