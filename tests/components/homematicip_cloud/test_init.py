"""Test HomematicIP Cloud setup process."""

from asynctest import CoroutineMock, patch

from homeassistant.components import homematicip_cloud as hmipc
from homeassistant.setup import async_setup_component

from tests.common import Mock, MockConfigEntry, mock_coro


async def test_config_with_accesspoint_passed_to_config_entry(hass):
    """Test that config for a accesspoint are loaded via config entry."""

    entry_config = {
        hmipc.CONF_ACCESSPOINT: "ABC123",
        hmipc.CONF_AUTHTOKEN: "123",
        hmipc.CONF_NAME: "name",
    }
    # no config_entry exists
    assert len(hass.config_entries.async_entries(hmipc.DOMAIN)) == 0
    # no acccesspoint exists
    assert not hass.data.get(hmipc.DOMAIN)

    assert (
        await async_setup_component(hass, hmipc.DOMAIN, {hmipc.DOMAIN: entry_config})
        is True
    )

    # config_entry created for access point
    config_entries = hass.config_entries.async_entries(hmipc.DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        "authtoken": "123",
        "hapid": "ABC123",
        "name": "name",
    }
    # defined access_point created for config_entry
    assert isinstance(hass.data[hmipc.DOMAIN]["ABC123"], hmipc.HomematicipHAP)


async def test_config_already_registered_not_passed_to_config_entry(hass):
    """Test that an already registered accesspoint does not get imported."""

    mock_config = {
        hmipc.HMIPC_AUTHTOKEN: "123",
        hmipc.HMIPC_HAPID: "ABC123",
        hmipc.HMIPC_NAME: "name",
    }
    MockConfigEntry(domain=hmipc.DOMAIN, data=mock_config).add_to_hass(hass)

    # one config_entry exists
    config_entries = hass.config_entries.async_entries(hmipc.DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        "authtoken": "123",
        "hapid": "ABC123",
        "name": "name",
    }
    # config_enty has no unique_id
    assert not config_entries[0].unique_id

    entry_config = {
        hmipc.CONF_ACCESSPOINT: "ABC123",
        hmipc.CONF_AUTHTOKEN: "123",
        hmipc.CONF_NAME: "name",
    }
    assert (
        await async_setup_component(hass, hmipc.DOMAIN, {hmipc.DOMAIN: entry_config})
        is True
    )

    # no new config_entry created / still one config_entry
    config_entries = hass.config_entries.async_entries(hmipc.DOMAIN)
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
    mock_config = {
        hmipc.HMIPC_AUTHTOKEN: "123",
        hmipc.HMIPC_HAPID: "ABC123",
        hmipc.HMIPC_NAME: "name",
    }
    MockConfigEntry(domain=hmipc.DOMAIN, data=mock_config).add_to_hass(hass)

    with patch.object(hmipc, "HomematicipHAP") as mock_hap:
        instance = mock_hap.return_value
        instance.async_setup.return_value = mock_coro(True)
        instance.home.id = "1"
        instance.home.modelType = "mock-type"
        instance.home.name = "mock-name"
        instance.home.currentAPVersion = "mock-ap-version"
        instance.async_reset.return_value = CoroutineMock(True)

        assert await async_setup_component(hass, hmipc.DOMAIN, {}) is True

    assert mock_hap.return_value.mock_calls[0][0] == "async_setup"

    config_entries = hass.config_entries.async_entries(hmipc.DOMAIN)
    assert len(config_entries) == 1

    await hass.config_entries.async_unload(config_entries[0].entry_id)

    assert len(mock_hap.return_value.async_reset.mock_calls) == 1
    # entry is unloaded
    assert hass.data[hmipc.DOMAIN] == {}


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
