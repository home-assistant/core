"""Test the Lovelace initialization."""
import os
import unittest
from unittest.mock import patch
from tempfile import mkdtemp
from ruamel.yaml import YAML

from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.components.lovelace import (load_yaml, migrate_config,
                                               save_yaml,
                                               UnsupportedYamlError)

TEST_YAML_A = """\
title: My Awesome Home
# Include external resources
resources:
  - url: /local/my-custom-card.js
    type: js
  - url: /local/my-webfont.css
    type: css

# Exclude entities from "Unused entities" view
excluded_entities:
  - weblink.router
views:
    # View tab title.
  - title: Example
    # Optional unique id for direct access /lovelace/${id}
    id: example
    # Optional background (overwrites the global background).
    background: radial-gradient(crimson, skyblue)
    # Each view can have a different theme applied.
    theme: dark-mode
    # The cards to show on this view.
    cards:
        # The filter card will filter entities for their state
      - type: entity-filter
        entities:
          - device_tracker.paulus
          - device_tracker.anne_there
        state_filter:
          - 'home'
        card:
          type: glance
          title: People that are home

        # The picture entity card will represent an entity with a picture
      - type: picture-entity
        image: https://www.home-assistant.io/images/default-social.png
        entity: light.bed_light

    # Specify a tab icon if you want the view tab to be an icon.
  - icon: mdi:home-assistant
    # Title of the view. Will be used as the tooltip for tab icon
    title: Second view
    cards:
      - id: test
        type: entities
        # Entities card will take a list of entities and show their state.
      - type: entities
        # Title of the entities card
        title: Example
        # The entities here will be shown in the same order as specified.
        # Each entry is an entity ID or a map with extra options.
        entities:
          - light.kitchen
          - switch.ac
          - entity: light.living_room
            # Override the name to use
            name: LR Lights

        # The markdown card will render markdown text.
      - type: markdown
        title: Lovelace
        content: >
          Welcome to your **Lovelace UI**.
"""

TEST_YAML_B = """\
title: Home
views:
  - title: Dashboard
    id: dashboard
    icon: mdi:home
    cards:
      - id: testid
        type: vertical-stack
        cards:
          - type: picture-entity
            entity: group.sample
            name: Sample
            image:  /local/images/sample.jpg
            tap_action: toggle
"""

# Test data that can not be loaded as YAML
TEST_BAD_YAML = """\
title: Home
views:
  - title: Dashboard
    icon: mdi:home
    cards:
      - id: testid
          type: vertical-stack
"""

# Test unsupported YAML
TEST_UNSUP_YAML = """\
title: Home
views:
  - title: Dashboard
    icon: mdi:home
    cards: !include cards.yaml
"""


class TestYAML(unittest.TestCase):
    """Test lovelace.yaml save and load."""

    def setUp(self):
        """Set up for tests."""
        self.tmp_dir = mkdtemp()
        self.yaml = YAML(typ='rt')

    def tearDown(self):
        """Clean up after tests."""
        for fname in os.listdir(self.tmp_dir):
            os.remove(os.path.join(self.tmp_dir, fname))
        os.rmdir(self.tmp_dir)

    def _path_for(self, leaf_name):
        return os.path.join(self.tmp_dir, leaf_name+".yaml")

    def test_save_and_load(self):
        """Test saving and loading back."""
        fname = self._path_for("test1")
        save_yaml(fname, self.yaml.load(TEST_YAML_A))
        data = load_yaml(fname)
        self.assertEqual(data, self.yaml.load(TEST_YAML_A))

    def test_overwrite_and_reload(self):
        """Test that we can overwrite an existing file and read back."""
        fname = self._path_for("test3")
        save_yaml(fname, self.yaml.load(TEST_YAML_A))
        save_yaml(fname, self.yaml.load(TEST_YAML_B))
        data = load_yaml(fname)
        self.assertEqual(data, self.yaml.load(TEST_YAML_B))

    def test_load_bad_data(self):
        """Test error from trying to load unserialisable data."""
        fname = self._path_for("test5")
        with open(fname, "w") as fh:
            fh.write(TEST_BAD_YAML)
        with self.assertRaises(HomeAssistantError):
            load_yaml(fname)

    def test_add_id(self):
        """Test if id is added."""
        fname = self._path_for("test6")
        with patch('homeassistant.components.lovelace.load_yaml',
                   return_value=self.yaml.load(TEST_YAML_A)), \
                patch('homeassistant.components.lovelace.save_yaml'):
            data = migrate_config(fname)
        assert 'id' in data['views'][0]['cards'][0]
        assert 'id' in data['views'][1]

    def test_id_not_changed(self):
        """Test if id is not changed if already exists."""
        fname = self._path_for("test7")
        with patch('homeassistant.components.lovelace.load_yaml',
                   return_value=self.yaml.load(TEST_YAML_B)):
            data = migrate_config(fname)
        assert data == self.yaml.load(TEST_YAML_B)


async def test_deprecated_lovelace_ui(hass, hass_ws_client):
    """Test lovelace_ui command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_config',
               return_value={'hello': 'world'}):
        await client.send_json({
            'id': 5,
            'type': 'frontend/lovelace_config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert msg['result'] == {'hello': 'world'}


async def test_deprecated_lovelace_ui_not_found(hass, hass_ws_client):
    """Test lovelace_ui command cannot find file."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_config',
               side_effect=FileNotFoundError):
        await client.send_json({
            'id': 5,
            'type': 'frontend/lovelace_config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'file_not_found'


async def test_deprecated_lovelace_ui_load_err(hass, hass_ws_client):
    """Test lovelace_ui command cannot find file."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_config',
               side_effect=HomeAssistantError):
        await client.send_json({
            'id': 5,
            'type': 'frontend/lovelace_config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'load_error'


async def test_lovelace_ui(hass, hass_ws_client):
    """Test lovelace_ui command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_config',
               return_value={'hello': 'world'}):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert msg['result'] == {'hello': 'world'}


async def test_lovelace_ui_not_found(hass, hass_ws_client):
    """Test lovelace_ui command cannot find file."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_config',
               side_effect=FileNotFoundError):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'file_not_found'


async def test_lovelace_ui_load_err(hass, hass_ws_client):
    """Test lovelace_ui command load error."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_config',
               side_effect=HomeAssistantError):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'load_error'


async def test_lovelace_ui_load_json_err(hass, hass_ws_client):
    """Test lovelace_ui command load error."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_config',
               side_effect=UnsupportedYamlError):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'unsupported_error'


async def test_lovelace_get_card(hass, hass_ws_client):
    """Test get_card command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.components.lovelace.load_yaml',
               return_value=yaml.load(TEST_YAML_A)):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/get',
            'card_id': 'test',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert msg['result'] == 'id: test\ntype: entities\n'


async def test_lovelace_get_card_not_found(hass, hass_ws_client):
    """Test get_card command cannot find card."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.components.lovelace.load_yaml',
               return_value=yaml.load(TEST_YAML_A)):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/get',
            'card_id': 'not_found',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'card_not_found'


async def test_lovelace_get_card_bad_yaml(hass, hass_ws_client):
    """Test get_card command bad yaml."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_yaml',
               side_effect=HomeAssistantError):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/get',
            'card_id': 'testid',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'load_error'


async def test_lovelace_update_card(hass, hass_ws_client):
    """Test update_card command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.components.lovelace.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.components.lovelace.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/update',
            'card_id': 'test',
            'card_config': 'id: test\ntype: glance\n',
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    assert result.mlget(['views', 1, 'cards', 0, 'type'],
                        list_ok=True) == 'glance'
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']


async def test_lovelace_update_card_not_found(hass, hass_ws_client):
    """Test update_card command cannot find card."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.components.lovelace.load_yaml',
               return_value=yaml.load(TEST_YAML_A)):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/update',
            'card_id': 'not_found',
            'card_config': 'id: test\ntype: glance\n',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'card_not_found'


async def test_lovelace_update_card_bad_yaml(hass, hass_ws_client):
    """Test update_card command bad yaml."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.components.lovelace.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.components.lovelace.yaml_to_object',
              side_effect=HomeAssistantError):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/update',
            'card_id': 'test',
            'card_config': 'id: test\ntype: glance\n',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'save_error'


async def test_lovelace_add_card(hass, hass_ws_client):
    """Test add_card command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.components.lovelace.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.components.lovelace.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/add',
            'view_id': 'example',
            'card_config': 'id: test\ntype: added\n',
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    assert result.mlget(['views', 0, 'cards', 2, 'type'],
                        list_ok=True) == 'added'
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']


async def test_lovelace_add_card_position(hass, hass_ws_client):
    """Test add_card command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.components.lovelace.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.components.lovelace.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/add',
            'view_id': 'example',
            'position': 0,
            'card_config': 'id: test\ntype: added\n',
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    assert result.mlget(['views', 0, 'cards', 0, 'type'],
                        list_ok=True) == 'added'
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
