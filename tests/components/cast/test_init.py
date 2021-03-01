"""Tests for the Cast config flow."""
from unittest.mock import ANY, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import cast
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_creating_entry_sets_up_media_player(hass):
    """Test setting up Cast loads the media player."""
    with patch(
        "homeassistant.components.cast.media_player.async_setup_entry",
        return_value=True,
    ) as mock_setup, patch(
        "pychromecast.discovery.discover_chromecasts", return_value=(True, None)
    ), patch(
        "pychromecast.discovery.stop_discovery"
    ):
        result = await hass.config_entries.flow.async_init(
            cast.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_cast_creates_entry(hass):
    """Test that specifying config will create an entry."""
    with patch(
        "homeassistant.components.cast.async_setup_entry", return_value=True
    ) as mock_setup:
        await async_setup_component(
            hass, cast.DOMAIN, {"cast": {"some_config": "to_trigger_import"}}
        )
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_not_configuring_cast_not_creates_entry(hass):
    """Test that no config will not create an entry."""
    with patch(
        "homeassistant.components.cast.async_setup_entry", return_value=True
    ) as mock_setup:
        await async_setup_component(hass, cast.DOMAIN, {})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0


@pytest.mark.parametrize("source", ["import", "user", "zeroconf"])
async def test_single_instance(hass, source):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain="cast").add_to_hass(hass)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        "cast", context={"source": source}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_user_setup(hass, mqtt_mock):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "cast", context={"source": "user"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    users = await hass.auth.async_get_users()
    assert len(users) == 1
    assert result["type"] == "create_entry"
    assert result["result"].data == {
        "known_hosts": [],
        "user_id": users[0].id,  # Home Assistant cast user
    }


async def test_user_setup_options(hass, mqtt_mock):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "cast", context={"source": "user"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"known_hosts": "192.168.0.1,  ,  192.168.0.2 "}
    )

    users = await hass.auth.async_get_users()
    assert len(users) == 1
    assert result["type"] == "create_entry"
    assert result["result"].data == {
        "known_hosts": ["192.168.0.1", "192.168.0.2"],
        "user_id": users[0].id,  # Home Assistant cast user
    }


async def test_zeroconf_setup(hass):
    """Test we can finish a config flow through zeroconf."""
    result = await hass.config_entries.flow.async_init(
        "cast", context={"source": "zeroconf"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    users = await hass.auth.async_get_users()
    assert len(users) == 1
    assert result["type"] == "create_entry"
    assert result["result"].data == {
        "known_hosts": None,
        "user_id": users[0].id,  # Home Assistant cast user
    }


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]


async def test_option_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain="cast", data={"known_hosts": ["192.168.0.10", "192.168.0.11"]}
    )
    config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "options"
    data_schema = result["data_schema"].schema
    assert get_suggested(data_schema, "known_hosts") == "192.168.0.10,192.168.0.11"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"known_hosts": "192.168.0.1,  ,  192.168.0.2 "},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] is None
    assert config_entry.data == {"known_hosts": ["192.168.0.1", "192.168.0.2"]}


async def test_known_hosts(hass, castbrowser_mock, castbrowser_constructor_mock):
    """Test known hosts is passed to pychromecasts."""
    result = await hass.config_entries.flow.async_init(
        "cast", context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"known_hosts": "192.168.0.1, 192.168.0.2"}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    config_entry = hass.config_entries.async_entries("cast")[0]

    assert castbrowser_mock.start_discovery.call_count == 1
    castbrowser_constructor_mock.assert_called_once_with(
        ANY, ANY, ["192.168.0.1", "192.168.0.2"]
    )
    castbrowser_mock.reset_mock()
    castbrowser_constructor_mock.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"known_hosts": "192.168.0.11, 192.168.0.12"},
    )

    await hass.async_block_till_done()

    castbrowser_mock.start_discovery.assert_not_called()
    castbrowser_constructor_mock.assert_not_called()
    castbrowser_mock.host_browser.update_hosts.assert_called_once_with(
        ["192.168.0.11", "192.168.0.12"]
    )
