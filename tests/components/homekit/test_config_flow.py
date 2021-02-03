"""Test the HomeKit config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.homekit.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME, CONF_PORT

from tests.common import MockConfigEntry


def _mock_config_entry_with_options_populated():
    """Create a mock config entry with options populated."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "filter": {
                "include_domains": [
                    "fan",
                    "humidifier",
                    "vacuum",
                    "media_player",
                    "climate",
                    "alarm_control_panel",
                ],
                "exclude_entities": ["climate.front_gate"],
            },
        },
    )


async def test_user_form(hass):
    """Test we can setup a new instance."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.homekit.config_flow.find_next_available_port",
        return_value=12345,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"include_domains": ["light"]},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "pairing"

    with patch(
        "homeassistant.components.homekit.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.homekit.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result3["title"][:11] == "HASS Bridge"
    bridge_name = (result3["title"].split(":"))[0]
    assert result3["data"] == {
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["light"],
            "include_entities": [],
        },
        "name": bridge_name,
        "port": 12345,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(hass):
    """Test we can import instance."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "port_name_in_use"

    with patch(
        "homeassistant.components.homekit.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.homekit.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_NAME: "othername", CONF_PORT: 56789},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "othername:56789"
    assert result2["data"] == {
        "name": "othername",
        "port": 56789,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 2


@pytest.mark.parametrize("auto_start", [True, False])
async def test_options_flow_exclude_mode_advanced(auto_start, hass):
    """Test config flow options in exclude mode with advanced options."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": True}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["fan", "vacuum", "climate", "humidifier"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "include_exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"entities": ["climate.old"], "include_exclude_mode": "exclude"},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "advanced"

    with patch("homeassistant.components.homekit.async_setup_entry", return_value=True):
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"auto_start": auto_start},
        )

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": auto_start,
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old"],
            "include_domains": ["fan", "vacuum", "climate", "humidifier"],
            "include_entities": [],
        },
    }


async def test_options_flow_exclude_mode_basic(hass):
    """Test config flow options in exclude mode."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["fan", "vacuum", "climate"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "include_exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"entities": ["climate.old"], "include_exclude_mode": "exclude"},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": True,
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old"],
            "include_domains": ["fan", "vacuum", "climate"],
            "include_entities": [],
        },
    }


async def test_options_flow_include_mode_basic(hass):
    """Test config flow options in include mode."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    hass.states.async_set("climate.new", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["fan", "vacuum", "climate"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "include_exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"entities": ["climate.new"], "include_exclude_mode": "include"},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": True,
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["fan", "vacuum"],
            "include_entities": ["climate.new"],
        },
    }


async def test_options_flow_exclude_mode_with_cameras(hass):
    """Test config flow options in exclude mode with cameras."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    hass.states.async_set("camera.native_h264", "off")
    hass.states.async_set("camera.transcode_h264", "off")
    hass.states.async_set("camera.excluded", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["fan", "vacuum", "climate", "camera"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "include_exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["climate.old", "camera.excluded"],
            "include_exclude_mode": "exclude",
        },
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_copy": ["camera.native_h264"]},
    )

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": True,
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old", "camera.excluded"],
            "include_domains": ["fan", "vacuum", "climate", "camera"],
            "include_entities": [],
        },
        "entity_config": {"camera.native_h264": {"video_codec": "copy"}},
    }

    # Now run though again and verify we can turn off copy

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["fan", "vacuum", "climate", "camera"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "include_exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["climate.old", "camera.excluded"],
            "include_exclude_mode": "exclude",
        },
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_copy": []},
    )

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": True,
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old", "camera.excluded"],
            "include_domains": ["fan", "vacuum", "climate", "camera"],
            "include_entities": [],
        },
        "entity_config": {"camera.native_h264": {}},
    }


async def test_options_flow_include_mode_with_cameras(hass):
    """Test config flow options in include mode with cameras."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    hass.states.async_set("camera.native_h264", "off")
    hass.states.async_set("camera.transcode_h264", "off")
    hass.states.async_set("camera.excluded", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["fan", "vacuum", "climate", "camera"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "include_exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["camera.native_h264", "camera.transcode_h264"],
            "include_exclude_mode": "include",
        },
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_copy": ["camera.native_h264"]},
    )

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": True,
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["fan", "vacuum", "climate"],
            "include_entities": ["camera.native_h264", "camera.transcode_h264"],
        },
        "entity_config": {"camera.native_h264": {"video_codec": "copy"}},
    }

    # Now run though again and verify we can turn off copy

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["fan", "vacuum", "climate", "camera"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "include_exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["climate.old", "camera.excluded"],
            "include_exclude_mode": "exclude",
        },
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_copy": []},
    )

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": True,
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old", "camera.excluded"],
            "include_domains": ["fan", "vacuum", "climate", "camera"],
            "include_entities": [],
        },
        "entity_config": {"camera.native_h264": {}},
    }


async def test_options_flow_blocked_when_from_yaml(hass):
    """Test config flow options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "auto_start": True,
            "filter": {
                "include_domains": [
                    "fan",
                    "humidifier",
                    "vacuum",
                    "media_player",
                    "climate",
                    "alarm_control_panel",
                ],
                "exclude_entities": ["climate.front_gate"],
            },
        },
        source=SOURCE_IMPORT,
    )
    config_entry.add_to_hass(hass)

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "yaml"

    with patch("homeassistant.components.homekit.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={},
        )
        assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_options_flow_include_mode_basic_accessory(hass):
    """Test config flow options in include mode with a single accessory."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("media_player.tv", "off")
    hass.states.async_set("media_player.sonos", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["media_player"], "mode": "accessory"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "include_exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"entities": "media_player.tv"},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": True,
        "mode": "accessory",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": [],
            "include_entities": ["media_player.tv"],
        },
    }
