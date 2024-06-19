"""Test the HomeKit config flow."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.homekit.const import (
    CONF_FILTER,
    DOMAIN,
    SHORT_BRIDGE_NAME,
)
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_IMPORT
from homeassistant.const import CONF_NAME, CONF_PORT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entityfilter import CONF_INCLUDE_DOMAINS
from homeassistant.setup import async_setup_component

from .util import PATH_HOMEKIT, async_init_entry

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


async def test_setup_in_bridge_mode(hass: HomeAssistant) -> None:
    """Test we can setup a new instance in bridge mode."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"include_domains": ["light"]},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pairing"

    with (
        patch(
            "homeassistant.components.homekit.config_flow.async_find_next_available_port",
            return_value=12345,
        ),
        patch(
            "homeassistant.components.homekit.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.homekit.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    bridge_name = (result3["title"].split(":"))[0]
    assert bridge_name == SHORT_BRIDGE_NAME
    assert result3["data"] == {
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["light"],
            "include_entities": [],
        },
        "exclude_accessory_mode": True,
        "mode": "bridge",
        "name": bridge_name,
        "port": 12345,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_setup_in_bridge_mode_name_taken(hass: HomeAssistant) -> None:
    """Test we can setup a new instance in bridge mode when the name is taken."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: SHORT_BRIDGE_NAME, CONF_PORT: 8000},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"include_domains": ["light"]},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pairing"

    with (
        patch(
            "homeassistant.components.homekit.config_flow.async_find_next_available_port",
            return_value=12345,
        ),
        patch(
            "homeassistant.components.homekit.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.homekit.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] != SHORT_BRIDGE_NAME
    assert result3["title"].startswith(SHORT_BRIDGE_NAME)
    bridge_name = (result3["title"].split(":"))[0]
    assert result3["data"] == {
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["light"],
            "include_entities": [],
        },
        "exclude_accessory_mode": True,
        "mode": "bridge",
        "name": bridge_name,
        "port": 12345,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 2


async def test_setup_creates_entries_for_accessory_mode_devices(
    hass: HomeAssistant,
) -> None:
    """Test we can setup a new instance and we create entries for accessory mode devices."""
    hass.states.async_set("camera.one", "on")
    hass.states.async_set("camera.existing", "on")
    hass.states.async_set("lock.new", "on")
    hass.states.async_set("media_player.two", "on", {"device_class": "tv"})
    hass.states.async_set("remote.standard", "on")
    hass.states.async_set("remote.activity", "on", {"supported_features": 4})

    bridge_mode_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "bridge", CONF_PORT: 8001},
        options={
            "mode": "bridge",
            "filter": {
                "include_entities": ["camera.existing"],
            },
        },
    )
    bridge_mode_entry.add_to_hass(hass)
    accessory_mode_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "accessory", CONF_PORT: 8000},
        options={
            "mode": "accessory",
            "filter": {
                "include_entities": ["camera.existing"],
            },
        },
    )
    accessory_mode_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"include_domains": ["camera", "media_player", "light", "lock", "remote"]},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pairing"

    with (
        patch(
            "homeassistant.components.homekit.config_flow.async_find_next_available_port",
            return_value=12345,
        ),
        patch(
            "homeassistant.components.homekit.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.homekit.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"][:11] == "HASS Bridge"
    bridge_name = (result3["title"].split(":"))[0]
    assert result3["data"] == {
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["media_player", "light", "lock", "remote"],
            "include_entities": [],
        },
        "exclude_accessory_mode": True,
        "mode": "bridge",
        "name": bridge_name,
        "port": 12345,
    }
    assert len(mock_setup.mock_calls) == 1
    #
    # Existing accessory mode entries should get setup but not duplicated
    #
    # 1 - existing accessory for camera.existing
    # 2 - existing bridge for camera.one
    # 3 - new bridge
    # 4 - camera.one in accessory mode
    # 5 - media_player.two in accessory mode
    # 6 - remote.activity in accessory mode
    # 7 - lock.new in accessory mode
    assert len(mock_setup_entry.mock_calls) == 7


async def test_import(hass: HomeAssistant) -> None:
    """Test we can import instance."""

    ignored_entry = MockConfigEntry(domain=DOMAIN, data={}, source=SOURCE_IGNORE)
    ignored_entry.add_to_hass(hass)
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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "port_name_in_use"

    with (
        patch(
            "homeassistant.components.homekit.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.homekit.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_NAME: "othername", CONF_PORT: 56789},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "othername:56789"
    assert result2["data"] == {
        "name": "othername",
        "port": 56789,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 2


async def test_options_flow_exclude_mode_advanced(hass: HomeAssistant) -> None:
    """Test config flow options in exclude mode with advanced options."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate", "humidifier"],
            "include_exclude_mode": "exclude",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"entities": ["climate.old"]},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "advanced"

    with patch("homeassistant.components.homekit.async_setup_entry", return_value=True):
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={},
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "devices": [],
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old"],
            "include_domains": ["fan", "vacuum", "climate", "humidifier"],
            "include_entities": [],
        },
    }


async def test_options_flow_exclude_mode_basic(hass: HomeAssistant) -> None:
    """Test config flow options in exclude mode."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    hass.states.async_set("climate.front_gate", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate"],
            "include_exclude_mode": "exclude",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "exclude"
    entities = result["data_schema"]({})["entities"]
    assert entities == ["climate.front_gate"]

    # Inject garbage to ensure the options data
    # is being deep copied and we cannot mutate it in flight
    config_entry.options[CONF_FILTER][CONF_INCLUDE_DOMAINS].append("garbage")

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"entities": ["climate.old"]},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old"],
            "include_domains": ["fan", "vacuum", "climate"],
            "include_entities": [],
        },
    }


@patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True)
@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_options_flow_devices(
    port_mock,
    hass: HomeAssistant,
    demo_cleanup,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test devices can be bridged."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "devices": ["notexist"],
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
    config_entry.add_to_hass(hass)

    demo_config_entry = MockConfigEntry(domain="domain")
    demo_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.homekit.HomeKit") as mock_homekit:
        mock_homekit.return_value = homekit = Mock()
        type(homekit).async_start = AsyncMock()
        assert await async_setup_component(hass, "homekit", {"homekit": {}})
        assert await async_setup_component(hass, "homeassistant", {})
        assert await async_setup_component(hass, "demo", {"demo": {}})
        assert await async_setup_component(hass, "homekit", {"homekit": {}})

        hass.states.async_set("climate.old", "off")
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            config_entry.entry_id, context={"show_advanced_options": True}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "domains": ["fan", "vacuum", "climate"],
                "include_exclude_mode": "exclude",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "exclude"

        entry = entity_registry.async_get("light.ceiling_lights")
        assert entry is not None
        device_id = entry.device_id

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "entities": ["climate.old"],
            },
        )

        with patch(
            "homeassistant.components.homekit.async_setup_entry", return_value=True
        ):
            result3 = await hass.config_entries.options.async_configure(
                result2["flow_id"],
                user_input={"devices": [device_id]},
            )

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert config_entry.options == {
            "devices": [device_id],
            "mode": "bridge",
            "filter": {
                "exclude_domains": [],
                "exclude_entities": ["climate.old"],
                "include_domains": ["fan", "vacuum", "climate"],
                "include_entities": [],
            },
        }

        await hass.async_block_till_done()
        await hass.config_entries.async_unload(config_entry.entry_id)


@patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True)
@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_options_flow_devices_preserved_when_advanced_off(
    port_mock, hass: HomeAssistant
) -> None:
    """Test devices are preserved if they were added in advanced mode but it was turned off."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "devices": ["1fabcabcabcabcabcabcabcabcabc"],
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
    config_entry.add_to_hass(hass)

    demo_config_entry = MockConfigEntry(domain="domain")
    demo_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.homekit.HomeKit") as mock_homekit:
        mock_homekit.return_value = homekit = Mock()
        type(homekit).async_start = AsyncMock()
        assert await async_setup_component(hass, "homekit", {"homekit": {}})

        hass.states.async_set("climate.old", "off")
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            config_entry.entry_id, context={"show_advanced_options": False}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "domains": ["fan", "vacuum", "climate"],
                "include_exclude_mode": "exclude",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "exclude"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "entities": ["climate.old"],
            },
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert config_entry.options == {
            "devices": ["1fabcabcabcabcabcabcabcabcabc"],
            "mode": "bridge",
            "filter": {
                "exclude_domains": [],
                "exclude_entities": ["climate.old"],
                "include_domains": ["fan", "vacuum", "climate"],
                "include_entities": [],
            },
        }
        await hass.async_block_till_done()
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_options_flow_include_mode_with_non_existant_entity(
    hass: HomeAssistant,
) -> None:
    """Test config flow options in include mode with a non-existent entity."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "filter": {
                "include_entities": ["climate.not_exist", "climate.front_gate"],
            },
        },
    )
    config_entry.add_to_hass(hass)
    hass.states.async_set("climate.front_gate", "off")
    hass.states.async_set("climate.new", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate"],
            "include_exclude_mode": "include",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"

    entities = result["data_schema"]({})["entities"]
    assert "climate.not_exist" not in entities

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["climate.new", "climate.front_gate"],
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["fan", "vacuum"],
            "include_entities": ["climate.new", "climate.front_gate"],
        },
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_exclude_mode_with_non_existant_entity(
    hass: HomeAssistant,
) -> None:
    """Test config flow options in exclude mode with a non-existent entity."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "filter": {
                "include_domains": ["climate"],
                "exclude_entities": ["climate.not_exist", "climate.front_gate"],
            },
        },
    )
    config_entry.add_to_hass(hass)
    hass.states.async_set("climate.front_gate", "off")
    hass.states.async_set("climate.new", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["climate"],
            "include_exclude_mode": "exclude",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "exclude"

    entities = result["data_schema"]({})["entities"]
    assert "climate.not_exist" not in entities

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["climate.new", "climate.front_gate"],
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.new", "climate.front_gate"],
            "include_domains": ["climate"],
            "include_entities": [],
        },
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_include_mode_basic(hass: HomeAssistant) -> None:
    """Test config flow options in include mode."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    hass.states.async_set("climate.new", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate"],
            "include_exclude_mode": "include",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"entities": ["climate.new"]},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["fan", "vacuum"],
            "include_entities": ["climate.new"],
        },
    }
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_exclude_mode_with_cameras(hass: HomeAssistant) -> None:
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate", "camera"],
            "include_exclude_mode": "exclude",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["climate.old", "camera.excluded"],
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_copy": ["camera.native_h264"]},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate", "camera"],
            "include_exclude_mode": "exclude",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "exclude"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["climate.old", "camera.excluded"],
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_copy": ["camera.native_h264"]},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY

    assert config_entry.options == {
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old", "camera.excluded"],
            "include_domains": ["fan", "vacuum", "climate", "camera"],
            "include_entities": [],
        },
        "entity_config": {"camera.native_h264": {"video_codec": "copy"}},
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_include_mode_with_cameras(hass: HomeAssistant) -> None:
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate", "camera"],
            "include_exclude_mode": "include",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["camera.native_h264", "camera.transcode_h264"],
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_copy": ["camera.native_h264"]},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["climate", "fan", "vacuum"],
            "include_entities": ["camera.native_h264", "camera.transcode_h264"],
        },
        "entity_config": {"camera.native_h264": {"video_codec": "copy"}},
    }

    # Now run though again and verify we can turn off copy

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        "domains": ["climate", "fan", "vacuum", "camera"],
        "mode": "bridge",
        "include_exclude_mode": "include",
    }
    schema = result["data_schema"].schema
    assert _get_schema_default(schema, "domains") == [
        "climate",
        "fan",
        "vacuum",
        "camera",
    ]
    assert _get_schema_default(schema, "mode") == "bridge"
    assert _get_schema_default(schema, "include_exclude_mode") == "include"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["climate", "fan", "vacuum", "camera"],
            "include_exclude_mode": "exclude",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "exclude"
    assert result["data_schema"]({}) == {
        "entities": ["camera.native_h264", "camera.transcode_h264"],
    }
    schema = result["data_schema"].schema
    assert _get_schema_default(schema, "entities") == [
        "camera.native_h264",
        "camera.transcode_h264",
    ]

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["climate.old", "camera.excluded"],
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"
    assert result2["data_schema"]({}) == {
        "camera_copy": ["camera.native_h264"],
        "camera_audio": [],
    }
    schema = result2["data_schema"].schema
    assert _get_schema_default(schema, "camera_copy") == ["camera.native_h264"]

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_copy": []},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "entity_config": {},
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old", "camera.excluded"],
            "include_domains": ["climate", "fan", "vacuum", "camera"],
            "include_entities": [],
        },
        "mode": "bridge",
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_with_camera_audio(hass: HomeAssistant) -> None:
    """Test config flow options with cameras that support audio."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    hass.states.async_set("camera.audio", "off")
    hass.states.async_set("camera.no_audio", "off")
    hass.states.async_set("camera.excluded", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate", "camera"],
            "include_exclude_mode": "include",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["camera.audio", "camera.no_audio"],
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_audio": ["camera.audio"]},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["climate", "fan", "vacuum"],
            "include_entities": ["camera.audio", "camera.no_audio"],
        },
        "entity_config": {"camera.audio": {"support_audio": True}},
    }

    # Now run though again and verify we can turn off audio

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        "domains": ["climate", "fan", "vacuum", "camera"],
        "mode": "bridge",
        "include_exclude_mode": "include",
    }
    schema = result["data_schema"].schema
    assert _get_schema_default(schema, "domains") == [
        "climate",
        "fan",
        "vacuum",
        "camera",
    ]
    assert _get_schema_default(schema, "mode") == "bridge"
    assert _get_schema_default(schema, "include_exclude_mode") == "include"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "include_exclude_mode": "exclude",
            "domains": ["climate", "fan", "vacuum", "camera"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "exclude"
    assert result["data_schema"]({}) == {
        "entities": ["camera.audio", "camera.no_audio"],
    }
    schema = result["data_schema"].schema
    assert _get_schema_default(schema, "entities") == [
        "camera.audio",
        "camera.no_audio",
    ]

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": ["climate.old", "camera.excluded"],
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"
    assert result2["data_schema"]({}) == {
        "camera_copy": [],
        "camera_audio": ["camera.audio"],
    }
    schema = result2["data_schema"].schema
    assert _get_schema_default(schema, "camera_audio") == ["camera.audio"]

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_audio": []},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "entity_config": {},
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["climate.old", "camera.excluded"],
            "include_domains": ["climate", "fan", "vacuum", "camera"],
            "include_entities": [],
        },
        "mode": "bridge",
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_blocked_when_from_yaml(hass: HomeAssistant) -> None:
    """Test config flow options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "devices": [],
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "yaml"

    with patch("homeassistant.components.homekit.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={},
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY
    await hass.config_entries.async_unload(config_entry.entry_id)


@patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True)
@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_options_flow_include_mode_basic_accessory(
    port_mock,
    hass: HomeAssistant,
    hk_driver,
) -> None:
    """Test config flow options in include mode with a single accessory."""
    config_entry = _mock_config_entry_with_options_populated()
    await async_init_entry(hass, config_entry)

    hass.states.async_set("media_player.tv", "off")
    hass.states.async_set("media_player.sonos", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        "domains": [
            "fan",
            "humidifier",
            "vacuum",
            "media_player",
            "climate",
            "alarm_control_panel",
        ],
        "mode": "bridge",
        "include_exclude_mode": "exclude",
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["media_player"], "mode": "accessory"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "accessory"
    assert _get_schema_default(result2["data_schema"].schema, "entities") is None

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"entities": "media_player.tv"},
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "accessory",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": [],
            "include_entities": ["media_player.tv"],
        },
    }

    # Now we check again to make sure the single entity is still
    # preselected

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        "domains": ["media_player"],
        "mode": "accessory",
        "include_exclude_mode": "include",
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["media_player"], "mode": "accessory"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "accessory"
    assert (
        _get_schema_default(result2["data_schema"].schema, "entities")
        == "media_player.tv"
    )

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"entities": "media_player.tv"},
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "accessory",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": [],
            "include_entities": ["media_player.tv"],
        },
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_converting_bridge_to_accessory_mode(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test we can convert a bridge to accessory mode."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"include_domains": ["light"]},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pairing"

    # We need to actually setup the config entry or the data
    # will not get migrated to options
    with (
        patch(
            "homeassistant.components.homekit.config_flow.async_find_next_available_port",
            return_value=12345,
        ),
        patch(
            "homeassistant.components.homekit.HomeKit.async_start",
            return_value=True,
        ) as mock_async_start,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"][:11] == "HASS Bridge"
    bridge_name = (result3["title"].split(":"))[0]
    assert result3["data"] == {
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["light"],
            "include_entities": [],
        },
        "exclude_accessory_mode": True,
        "mode": "bridge",
        "name": bridge_name,
        "port": 12345,
    }
    assert len(mock_async_start.mock_calls) == 1

    config_entry = result3["result"]

    hass.states.async_set("camera.tv", "off")
    hass.states.async_set("camera.sonos", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert _get_schema_default(schema, "mode") == "bridge"
    assert _get_schema_default(schema, "domains") == ["light"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["camera"], "mode": "accessory"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "accessory"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"entities": "camera.tv"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"

    with (
        patch(
            "homeassistant.components.homekit.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch("homeassistant.components.homekit.async_port_is_available"),
    ):
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"camera_copy": ["camera.tv"]},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "entity_config": {"camera.tv": {"video_codec": "copy"}},
        "mode": "accessory",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": [],
            "include_entities": ["camera.tv"],
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


def _get_schema_default(schema, key_name):
    """Iterate schema to find a key."""
    for schema_key in schema:
        if schema_key == key_name:
            return schema_key.default()
    raise KeyError(f"{key_name} not found in schema")


@patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True)
@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_options_flow_exclude_mode_skips_category_entities(
    port_mock,
    hass: HomeAssistant,
    hk_driver,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ensure exclude mode does not offer category entities."""
    config_entry = _mock_config_entry_with_options_populated()
    await async_init_entry(hass, config_entry)

    hass.states.async_set("media_player.tv", "off")
    hass.states.async_set("media_player.sonos", "off")
    hass.states.async_set("switch.other", "off")

    sonos_config_switch = entity_registry.async_get_or_create(
        "switch",
        "sonos",
        "config",
        device_id="1234",
        entity_category=EntityCategory.CONFIG,
    )
    hass.states.async_set(sonos_config_switch.entity_id, "off")

    sonos_notconfig_switch = entity_registry.async_get_or_create(
        "switch",
        "sonos",
        "notconfig",
        device_id="1234",
        entity_category=None,
    )
    hass.states.async_set(sonos_notconfig_switch.entity_id, "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        "domains": [
            "fan",
            "humidifier",
            "vacuum",
            "media_player",
            "climate",
            "alarm_control_panel",
        ],
        "mode": "bridge",
        "include_exclude_mode": "exclude",
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["media_player", "switch"],
            "mode": "bridge",
            "include_exclude_mode": "exclude",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "exclude"
    assert _get_schema_default(result2["data_schema"].schema, "entities") == []

    # sonos_config_switch.entity_id is a config category entity
    # so it should not be selectable since it will always be excluded
    with pytest.raises(vol.error.Invalid):
        await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"entities": [sonos_config_switch.entity_id]},
        )

    result4 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={
            "entities": [
                "media_player.tv",
                "switch.other",
                sonos_notconfig_switch.entity_id,
            ]
        },
    )
    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [
                "media_player.tv",
                "switch.other",
                sonos_notconfig_switch.entity_id,
            ],
            "include_domains": ["media_player", "switch"],
            "include_entities": [],
        },
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


@patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True)
@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_options_flow_exclude_mode_skips_hidden_entities(
    port_mock,
    hass: HomeAssistant,
    hk_driver,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ensure exclude mode does not offer hidden entities."""
    config_entry = _mock_config_entry_with_options_populated()
    await async_init_entry(hass, config_entry)

    hass.states.async_set("media_player.tv", "off")
    hass.states.async_set("media_player.sonos", "off")
    hass.states.async_set("switch.other", "off")

    sonos_hidden_switch = entity_registry.async_get_or_create(
        "switch",
        "sonos",
        "config",
        device_id="1234",
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )
    hass.states.async_set(sonos_hidden_switch.entity_id, "off")
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        "domains": [
            "fan",
            "humidifier",
            "vacuum",
            "media_player",
            "climate",
            "alarm_control_panel",
        ],
        "mode": "bridge",
        "include_exclude_mode": "exclude",
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["media_player", "switch"],
            "mode": "bridge",
            "include_exclude_mode": "exclude",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "exclude"
    assert _get_schema_default(result2["data_schema"].schema, "entities") == []

    # sonos_hidden_switch.entity_id is a hidden entity
    # so it should not be selectable since it will always be excluded
    with pytest.raises(vol.error.Invalid):
        await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"entities": [sonos_hidden_switch.entity_id]},
        )

    result4 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"entities": ["media_player.tv", "switch.other"]},
    )
    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": ["media_player.tv", "switch.other"],
            "include_domains": ["media_player", "switch"],
            "include_entities": [],
        },
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


@patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True)
@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_options_flow_include_mode_allows_hidden_entities(
    port_mock,
    hass: HomeAssistant,
    hk_driver,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ensure include mode does not offer hidden entities."""
    config_entry = _mock_config_entry_with_options_populated()
    await async_init_entry(hass, config_entry)

    hass.states.async_set("media_player.tv", "off")
    hass.states.async_set("media_player.sonos", "off")
    hass.states.async_set("switch.other", "off")

    sonos_hidden_switch = entity_registry.async_get_or_create(
        "switch",
        "sonos",
        "config",
        device_id="1234",
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )
    hass.states.async_set(sonos_hidden_switch.entity_id, "off")
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        "domains": [
            "fan",
            "humidifier",
            "vacuum",
            "media_player",
            "climate",
            "alarm_control_panel",
        ],
        "mode": "bridge",
        "include_exclude_mode": "exclude",
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["media_player", "switch"],
            "mode": "bridge",
            "include_exclude_mode": "include",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "include"
    assert _get_schema_default(result2["data_schema"].schema, "entities") == []

    # sonos_hidden_switch.entity_id is a hidden entity
    # we allow it to be selected in include mode only
    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={
            "entities": [
                sonos_hidden_switch.entity_id,
                "media_player.tv",
                "switch.other",
            ]
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": [],
            "include_entities": [
                sonos_hidden_switch.entity_id,
                "media_player.tv",
                "switch.other",
            ],
        },
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)
