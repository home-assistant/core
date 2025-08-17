"""Tests for the Cast config flow."""

from unittest.mock import ANY, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import cast
from homeassistant.components.cast.home_assistant_cast import CAST_USER_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, get_schema_suggested_value


async def test_creating_entry_sets_up_media_player(hass: HomeAssistant) -> None:
    """Test setting up Cast loads the media player."""
    with (
        patch(
            "homeassistant.components.cast.media_player.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        patch("pychromecast.discovery.discover_chromecasts", return_value=(True, None)),
        patch(
            "pychromecast.discovery.stop_discovery",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            cast.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize(
    "source",
    [
        config_entries.SOURCE_USER,
        config_entries.SOURCE_ZEROCONF,
    ],
)
async def test_single_instance(hass: HomeAssistant, source) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(domain="cast").add_to_hass(hass)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        "cast", context={"source": source}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_setup(hass: HomeAssistant) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "cast", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    users = await hass.auth.async_get_users()
    assert next(user for user in users if user.name == CAST_USER_NAME)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "ignore_cec": [],
        "known_hosts": [],
        "uuid": [],
        "user_id": users[0].id,  # Home Assistant cast user
    }


async def test_user_setup_options(hass: HomeAssistant) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "cast", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"known_hosts": ["192.168.0.1", "", " ", "192.168.0.2 "]}
    )

    users = await hass.auth.async_get_users()
    assert next(user for user in users if user.name == CAST_USER_NAME)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "ignore_cec": [],
        "known_hosts": ["192.168.0.1", "192.168.0.2"],
        "uuid": [],
        "user_id": users[0].id,  # Home Assistant cast user
    }


async def test_zeroconf_setup(hass: HomeAssistant) -> None:
    """Test we can finish a config flow through zeroconf."""
    result = await hass.config_entries.flow.async_init(
        "cast", context={"source": config_entries.SOURCE_ZEROCONF}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    users = await hass.auth.async_get_users()
    assert next(user for user in users if user.name == CAST_USER_NAME)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "ignore_cec": [],
        "known_hosts": [],
        "uuid": [],
        "user_id": users[0].id,  # Home Assistant cast user
    }


async def test_zeroconf_setup_onboarding(hass: HomeAssistant) -> None:
    """Test we automatically finish a config flow through zeroconf during onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=False
    ):
        result = await hass.config_entries.flow.async_init(
            "cast", context={"source": config_entries.SOURCE_ZEROCONF}
        )

    users = await hass.auth.async_get_users()
    assert next(user for user in users if user.name == CAST_USER_NAME)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "ignore_cec": [],
        "known_hosts": [],
        "uuid": [],
        "user_id": users[0].id,  # Home Assistant cast user
    }


@pytest.mark.parametrize(
    ("parameter", "initial", "suggested", "user_input", "updated"),
    [
        (
            "known_hosts",
            ["192.168.0.10", "192.168.0.11"],
            ["192.168.0.10", "192.168.0.11"],
            ["192.168.0.1", " ", "  192.168.0.2 "],
            ["192.168.0.1", "192.168.0.2"],
        ),
        (
            "uuid",
            ["bla", "blu"],
            "bla,blu",
            "foo,  ,  bar ",
            ["foo", "bar"],
        ),
        (
            "ignore_cec",
            ["cast1", "cast2"],
            "cast1,cast2",
            "other_cast,  ,  some_cast ",
            ["other_cast", "some_cast"],
        ),
    ],
)
async def test_option_flow(
    hass: HomeAssistant,
    parameter: str,
    initial: list[str],
    suggested: str | list[str],
    user_input: str | list[str],
    updated: list[str],
) -> None:
    """Test config flow options."""
    basic_parameters = ["known_hosts"]
    advanced_parameters = ["ignore_cec", "uuid"]

    data = {
        "ignore_cec": [],
        "known_hosts": [],
        "uuid": [],
    }
    data[parameter] = initial
    config_entry = MockConfigEntry(domain="cast", data=data)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test ignore_cec and uuid options are hidden if advanced options are disabled
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "basic_options"
    data_schema = result["data_schema"].schema
    assert set(data_schema) == {"known_hosts"}
    orig_data = dict(config_entry.data)

    # Reconfigure known_hosts
    context = {"source": config_entries.SOURCE_USER, "show_advanced_options": True}
    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context=context
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "basic_options"
    data_schema = result["data_schema"].schema
    for other_param in basic_parameters:
        if other_param == parameter:
            continue
        assert get_schema_suggested_value(data_schema, other_param) == []
    if parameter in basic_parameters:
        assert get_schema_suggested_value(data_schema, parameter) == suggested

    user_input_dict = {}
    if parameter in basic_parameters:
        user_input_dict[parameter] = user_input
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input_dict,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "advanced_options"
    for other_param in basic_parameters:
        if other_param == parameter:
            continue
        assert config_entry.data[other_param] == []
    # No update yet
    assert config_entry.data[parameter] == initial

    # Reconfigure ignore_cec, uuid
    data_schema = result["data_schema"].schema
    for other_param in advanced_parameters:
        if other_param == parameter:
            continue
        assert get_schema_suggested_value(data_schema, other_param) == ""
    if parameter in advanced_parameters:
        assert get_schema_suggested_value(data_schema, parameter) == suggested

    user_input_dict = {}
    if parameter in advanced_parameters:
        user_input_dict[parameter] = user_input
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input_dict,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    for other_param in advanced_parameters:
        if other_param == parameter:
            continue
        assert config_entry.data[other_param] == []
    assert config_entry.data[parameter] == updated

    # Clear known_hosts
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    expected_data = {**orig_data, "known_hosts": []}
    if parameter in advanced_parameters:
        expected_data[parameter] = updated
    assert dict(config_entry.data) == expected_data


async def test_known_hosts(hass: HomeAssistant, castbrowser_mock) -> None:
    """Test known hosts is passed to pychromecasts."""
    result = await hass.config_entries.flow.async_init(
        "cast", context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"known_hosts": ["192.168.0.1", "192.168.0.2"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    config_entry = hass.config_entries.async_entries("cast")[0]

    assert castbrowser_mock.return_value.start_discovery.call_count == 1
    castbrowser_mock.assert_called_once_with(ANY, ANY, ["192.168.0.1", "192.168.0.2"])
    castbrowser_mock.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"known_hosts": ["192.168.0.11", "192.168.0.12"]},
    )

    await hass.async_block_till_done(wait_background_tasks=True)

    castbrowser_mock.return_value.start_discovery.assert_not_called()
    castbrowser_mock.assert_not_called()
    castbrowser_mock.return_value.host_browser.update_hosts.assert_called_once_with(
        ["192.168.0.11", "192.168.0.12"]
    )
