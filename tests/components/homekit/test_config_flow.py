"""Test the HomeKit config flow."""
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.homekit.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME, CONF_PORT

from tests.async_mock import patch
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
            "auto_start": False,
            "safe_mode": False,
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
            result["flow_id"], {"auto_start": True, "include_domains": ["light"]},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "pairing"

    with patch(
        "homeassistant.components.homekit.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.homekit.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result3["title"][:11] == "HASS Bridge"
    bridge_name = (result3["title"].split(":"))[0]
    assert result3["data"] == {
        "auto_start": True,
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["light"],
            "include_entities": [],
        },
        "name": bridge_name,
        "port": 12345,
    }
    await hass.async_block_till_done()
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
        "homeassistant.components.homekit.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_NAME: "othername", CONF_PORT: 56789},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "othername:56789"
    assert result2["data"] == {
        "name": "othername",
        "port": 56789,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 2


async def test_options_flow_advanced(hass):
    """Test config flow options."""

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
        user_input={"include_domains": ["fan", "vacuum", "climate", "humidifier"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"exclude_entities": ["climate.old"]},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "advanced"

    with patch("homeassistant.components.homekit.async_setup_entry", return_value=True):
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"], user_input={"auto_start": True, "safe_mode": True},
        )

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": True,
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old"],
            "include_domains": ["fan", "vacuum", "climate", "humidifier"],
            "include_entities": [],
        },
        "safe_mode": True,
    }


async def test_options_flow_basic(hass):
    """Test config flow options."""

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
        result["flow_id"], user_input={"include_domains": ["fan", "vacuum", "climate"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"exclude_entities": ["climate.old"]},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "advanced"

    with patch("homeassistant.components.homekit.async_setup_entry", return_value=True):
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"], user_input={"safe_mode": True},
        )

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": False,
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old"],
            "include_domains": ["fan", "vacuum", "climate"],
            "include_entities": [],
        },
        "safe_mode": True,
    }


async def test_options_flow_with_cameras(hass):
    """Test config flow options."""

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
        user_input={"include_domains": ["fan", "vacuum", "climate", "camera"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"exclude_entities": ["climate.old", "camera.excluded"]},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"], user_input={"camera_copy": ["camera.native_h264"]},
    )

    assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result3["step_id"] == "advanced"

    with patch("homeassistant.components.homekit.async_setup_entry", return_value=True):
        result4 = await hass.config_entries.options.async_configure(
            result3["flow_id"], user_input={"safe_mode": True},
        )

    assert result4["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": False,
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old", "camera.excluded"],
            "include_domains": ["fan", "vacuum", "climate", "camera"],
            "include_entities": [],
        },
        "entity_config": {"camera.native_h264": {"video_codec": "copy"}},
        "safe_mode": True,
    }

    # Now run though again and verify we can turn off copy

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"include_domains": ["fan", "vacuum", "climate", "camera"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"exclude_entities": ["climate.old", "camera.excluded"]},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"], user_input={"camera_copy": []},
    )

    assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result3["step_id"] == "advanced"

    with patch("homeassistant.components.homekit.async_setup_entry", return_value=True):
        result4 = await hass.config_entries.options.async_configure(
            result3["flow_id"], user_input={"safe_mode": True},
        )

    assert result4["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        "auto_start": False,
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old", "camera.excluded"],
            "include_domains": ["fan", "vacuum", "climate", "camera"],
            "include_entities": [],
        },
        "entity_config": {"camera.native_h264": {}},
        "safe_mode": True,
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
            "safe_mode": False,
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
            result["flow_id"], user_input={},
        )
        assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
