"""Test the IntelliFire config flow."""


from homeassistant.components.intellifire.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_pseudo_migration_good(
    hass: HomeAssistant,
    mock_config_entry_old,
    mock_login_with_credentials,
    mock_cloud_api_interface_user_data_1,
    mock_local_poll_data,
    mock_cloud_poll,
    mock_connectivity_test_pass_pass,
):
    """Test entity update from old Version1 to newer Versio1."""
    mock_config_entry_old.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_old.entry_id)

    assert mock_config_entry_old.data == {
        "ip_address": "192.168.2.108",
        "api_key": "B5C4DA27AAEF31D1FB21AFF9BFA6BCD2",
        "serial": "3FB284769E4736F30C8973A7ED358123",
        "auth_cookie": "B984F21A6378560019F8A1CDE41B6782",
        "web_client_id": "FA2B1C3045601234D0AE17D72F8E975",
        "user_id": "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        "username": "grumpypanda@china.cn",
        "password": "you-stole-my-pandas",
    }


async def test_connectivity_bad(
    hass: HomeAssistant,
    mock_config_entry_current,
    mock_login_with_credentials,
    mock_cloud_api_interface_user_data_1,
    mock_connectivity_test_fail_fail,
):
    """Test entity update from older Version1 to a newer Version1 with serial that can't be detected."""
    mock_config_entry_current.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_current.entry_id)

    # assert await hass.config_entries.async_setup(mock_config_entry_current.entry_id) is True
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_pseudo_migration_bad_title(
    hass: HomeAssistant,
    mock_config_entry_v1_bad_title,
    mock_login_with_credentials,
    mock_cloud_api_interface_user_data_1,
    mock_local_poll_data,
    mock_cloud_poll,
    mock_connectivity_test_pass_pass,
):
    """Test entity update from older Version1 to a newer Version1 with serial that can't be detected."""
    mock_config_entry_v1_bad_title.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v1_bad_title.entry_id)

    assert mock_config_entry_v1_bad_title.data == {
        "ip_address": "192.168.2.108",
        "api_key": "B5C4DA27AAEF31D1FB21AFF9BFA6BCD2",
        "serial": "3FB284769E4736F30C8973A7ED358123",
        "auth_cookie": "B984F21A6378560019F8A1CDE41B6782",
        "web_client_id": "FA2B1C3045601234D0AE17D72F8E975",
        "user_id": "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        "username": "grumpypanda@china.cn",
        "password": "you-stole-my-pandas",
    }


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry_current,
    mock_login_with_credentials,
    mock_cloud_api_interface_user_data_1,
    mock_connectivity_test_fail_fail_then_pass_pass,
):
    """Test reauth."""
    mock_config_entry_current.add_to_hass(hass)

    mock_config_entry_current.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reauth",
            "unique_id": mock_config_entry_current.unique_id,
            "entry_id": mock_config_entry_current.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM
    result["step_id"] = "cloud_api"
