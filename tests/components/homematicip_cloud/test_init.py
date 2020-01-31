"""Test HomematicIP Cloud setup process."""

from asynctest import CoroutineMock, Mock, patch

from homeassistant.components.homematicip_cloud.const import (
    CONF_ACCESSPOINT,
    CONF_AUTHTOKEN,
    DOMAIN as HMIPC_DOMAIN,
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
)
from homeassistant.components.homematicip_cloud.hap import HomematicipHAP
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED
from homeassistant.const import CONF_NAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_config_with_accesspoint_passed_to_config_entry(hass):
    """Test that config for a accesspoint are loaded via config entry."""

    entry_config = {
        CONF_ACCESSPOINT: "ABC123",
        CONF_AUTHTOKEN: "123",
        CONF_NAME: "name",
    }
    # no config_entry exists
    assert len(hass.config_entries.async_entries(HMIPC_DOMAIN)) == 0
    # no acccesspoint exists
    assert not hass.data.get(HMIPC_DOMAIN)

    assert (
        await async_setup_component(hass, HMIPC_DOMAIN, {HMIPC_DOMAIN: entry_config})
        is True
    )

    # config_entry created for access point
    config_entries = hass.config_entries.async_entries(HMIPC_DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        "authtoken": "123",
        "hapid": "ABC123",
        "name": "name",
    }
    # defined access_point created for config_entry
    assert isinstance(hass.data[HMIPC_DOMAIN]["ABC123"], HomematicipHAP)


async def test_config_already_registered_not_passed_to_config_entry(hass):
    """Test that an already registered accesspoint does not get imported."""

    mock_config = {HMIPC_AUTHTOKEN: "123", HMIPC_HAPID: "ABC123", HMIPC_NAME: "name"}
    MockConfigEntry(domain=HMIPC_DOMAIN, data=mock_config).add_to_hass(hass)

    # one config_entry exists
    config_entries = hass.config_entries.async_entries(HMIPC_DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        "authtoken": "123",
        "hapid": "ABC123",
        "name": "name",
    }
    # config_enty has no unique_id
    assert not config_entries[0].unique_id

    entry_config = {
        CONF_ACCESSPOINT: "ABC123",
        CONF_AUTHTOKEN: "123",
        CONF_NAME: "name",
    }
    assert (
        await async_setup_component(hass, HMIPC_DOMAIN, {HMIPC_DOMAIN: entry_config})
        is True
    )

    # no new config_entry created / still one config_entry
    config_entries = hass.config_entries.async_entries(HMIPC_DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        "authtoken": "123",
        "hapid": "ABC123",
        "name": "name",
    }
    # config_enty updated with unique_id
    assert config_entries[0].unique_id == "ABC123"


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    mock_config = {HMIPC_AUTHTOKEN: "123", HMIPC_HAPID: "ABC123", HMIPC_NAME: "name"}
    MockConfigEntry(domain=HMIPC_DOMAIN, data=mock_config).add_to_hass(hass)

    with patch("homeassistant.components.homematicip_cloud.HomematicipHAP") as mock_hap:
        instance = mock_hap.return_value
        instance.async_setup = CoroutineMock(return_value=True)
        instance.home.id = "1"
        instance.home.modelType = "mock-type"
        instance.home.name = "mock-name"
        instance.home.currentAPVersion = "mock-ap-version"
        instance.async_reset = CoroutineMock(return_value=True)

        assert await async_setup_component(hass, HMIPC_DOMAIN, {}) is True

    assert mock_hap.return_value.mock_calls[0][0] == "async_setup"

    assert hass.data[HMIPC_DOMAIN]["ABC123"]
    config_entries = hass.config_entries.async_entries(HMIPC_DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].state == ENTRY_STATE_LOADED
    await hass.config_entries.async_unload(config_entries[0].entry_id)
    assert config_entries[0].state == ENTRY_STATE_NOT_LOADED
    assert mock_hap.return_value.mock_calls[3][0] == "async_reset"
    # entry is unloaded
    assert hass.data[HMIPC_DOMAIN] == {}


async def test_hmip_dump_hap_config_services(hass, mock_hap_with_service):
    """Test dump configuration services."""

    with patch("pathlib.Path.write_text", return_value=Mock()) as write_mock:
        await hass.services.async_call(
            "homematicip_cloud", "dump_hap_config", {"anonymize": True}, blocking=True
        )
        home = mock_hap_with_service.home
        assert home.mock_calls[-1][0] == "download_configuration"
        assert home.mock_calls
        assert write_mock.mock_calls
