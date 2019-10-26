"""Test HomematicIP Cloud setup process."""

import os
from unittest.mock import patch

from homeassistant.components import homematicip_cloud as hmipc
from homeassistant.components.homematicip_cloud import DEFAULT_CONFIG_FILE_PREFIX
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro


async def test_config_with_accesspoint_passed_to_config_entry(hass):
    """Test that config for a accesspoint are loaded via config entry."""
    with patch.object(hass, "config_entries") as mock_config_entries, patch.object(
        hmipc, "configured_haps", return_value=[]
    ):
        assert (
            await async_setup_component(
                hass,
                hmipc.DOMAIN,
                {
                    hmipc.DOMAIN: {
                        hmipc.CONF_ACCESSPOINT: "ABC123",
                        hmipc.CONF_AUTHTOKEN: "123",
                        hmipc.CONF_NAME: "name",
                    }
                },
            )
            is True
        )

    # Flow started for the access point
    assert len(mock_config_entries.flow.mock_calls) >= 2


async def test_config_already_registered_not_passed_to_config_entry(hass):
    """Test that an already registered accesspoint does not get imported."""
    with patch.object(hass, "config_entries") as mock_config_entries, patch.object(
        hmipc, "configured_haps", return_value=["ABC123"]
    ):
        assert (
            await async_setup_component(
                hass,
                hmipc.DOMAIN,
                {
                    hmipc.DOMAIN: {
                        hmipc.CONF_ACCESSPOINT: "ABC123",
                        hmipc.CONF_AUTHTOKEN: "123",
                        hmipc.CONF_NAME: "name",
                    }
                },
            )
            is True
        )

    # No flow started
    assert not mock_config_entries.flow.mock_calls


async def test_setup_entry_successful(hass):
    """Test setup entry is successful."""
    entry = MockConfigEntry(
        domain=hmipc.DOMAIN,
        data={
            hmipc.HMIPC_HAPID: "ABC123",
            hmipc.HMIPC_AUTHTOKEN: "123",
            hmipc.HMIPC_NAME: "hmip",
        },
    )
    entry.add_to_hass(hass)
    with patch.object(hmipc, "HomematicipHAP") as mock_hap:
        instance = mock_hap.return_value
        instance.async_setup.return_value = mock_coro(True)
        instance.home.id = "1"
        instance.home.modelType = "mock-type"
        instance.home.name = "mock-name"
        instance.home.currentAPVersion = "mock-ap-version"

        assert (
            await async_setup_component(
                hass,
                hmipc.DOMAIN,
                {
                    hmipc.DOMAIN: {
                        hmipc.CONF_ACCESSPOINT: "ABC123",
                        hmipc.CONF_AUTHTOKEN: "123",
                        hmipc.CONF_NAME: "hmip",
                    }
                },
            )
            is True
        )

    assert len(mock_hap.mock_calls) >= 2


async def test_setup_defined_accesspoint(hass):
    """Test we initiate config entry for the accesspoint."""
    with patch.object(hass, "config_entries") as mock_config_entries, patch.object(
        hmipc, "configured_haps", return_value=[]
    ):
        mock_config_entries.flow.async_init.return_value = mock_coro()
        assert (
            await async_setup_component(
                hass,
                hmipc.DOMAIN,
                {
                    hmipc.DOMAIN: {
                        hmipc.CONF_ACCESSPOINT: "ABC123",
                        hmipc.CONF_AUTHTOKEN: "123",
                        hmipc.CONF_NAME: "hmip",
                    }
                },
            )
            is True
        )

    assert len(mock_config_entries.flow.mock_calls) == 1
    assert mock_config_entries.flow.mock_calls[0][2]["data"] == {
        hmipc.HMIPC_HAPID: "ABC123",
        hmipc.HMIPC_AUTHTOKEN: "123",
        hmipc.HMIPC_NAME: "hmip",
    }


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=hmipc.DOMAIN,
        data={
            hmipc.HMIPC_HAPID: "ABC123",
            hmipc.HMIPC_AUTHTOKEN: "123",
            hmipc.HMIPC_NAME: "hmip",
        },
    )
    entry.add_to_hass(hass)

    with patch.object(hmipc, "HomematicipHAP") as mock_hap:
        instance = mock_hap.return_value
        instance.async_setup.return_value = mock_coro(True)
        instance.home.id = "1"
        instance.home.modelType = "mock-type"
        instance.home.name = "mock-name"
        instance.home.currentAPVersion = "mock-ap-version"

        assert await async_setup_component(hass, hmipc.DOMAIN, {}) is True

    assert len(mock_hap.return_value.mock_calls) >= 1

    mock_hap.return_value.async_reset.return_value = mock_coro(True)
    assert await hmipc.async_unload_entry(hass, entry)
    assert len(mock_hap.return_value.async_reset.mock_calls) == 1
    assert hass.data[hmipc.DOMAIN] == {}


async def test_hmip_dump_hap_config_services(hass, mock_hap_with_service):
    """Test dump configuration services."""
    config_file = f"{hass.config.config_dir}/{DEFAULT_CONFIG_FILE_PREFIX}"
    try:
        await hass.services.async_call(
            "homematicip_cloud", "dump_hap_config", {"anonymize": True}, blocking=True
        )
        home = mock_hap_with_service.home
        assert home.mock_calls[-1][0] == "download_configuration"
        assert len(home.mock_calls) == 8  # pylint: disable=W0212

        assert os.path.isfile(config_file)
        file_content = open(config_file, "r").readlines()
        assert file_content
    finally:
        os.remove(config_file)
        assert not os.path.isfile(config_file)
