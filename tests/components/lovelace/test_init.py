"""Test the Lovelace initialization."""
from unittest.mock import patch
from ruamel.yaml import YAML

from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.components.lovelace import migrate_config
from homeassistant.util.ruamel_yaml import UnsupportedYamlError

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
        title: Test card
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


def test_add_id():
    """Test if id is added."""
    yaml = YAML(typ='rt')

    fname = "dummy.yaml"
    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
            patch('homeassistant.util.ruamel_yaml.save_yaml') \
            as save_yaml_mock:
        migrate_config(fname)

    result = save_yaml_mock.call_args_list[0][0][1]
    assert 'id' in result['views'][0]['cards'][0]
    assert 'id' in result['views'][1]


def test_id_not_changed():
    """Test if id is not changed if already exists."""
    yaml = YAML(typ='rt')

    fname = "dummy.yaml"
    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_B)), \
            patch('homeassistant.util.ruamel_yaml.save_yaml') \
            as save_yaml_mock:
        migrate_config(fname)
    assert save_yaml_mock.call_count == 0


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
    assert msg['error']['code'] == 'error'


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
    assert msg['error']['code'] == 'error'


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

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
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
    assert msg['result'] == 'id: test\ntype: entities\ntitle: Test card\n'


async def test_lovelace_get_card_not_found(hass, hass_ws_client):
    """Test get_card command cannot find card."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
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

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
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
    assert msg['error']['code'] == 'error'


async def test_lovelace_update_card(hass, hass_ws_client):
    """Test update_card command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
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

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
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

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.yaml_to_object',
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
    assert msg['error']['code'] == 'error'


async def test_lovelace_add_card(hass, hass_ws_client):
    """Test add_card command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
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

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
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


async def test_lovelace_move_card_position(hass, hass_ws_client):
    """Test move_card command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/move',
            'card_id': 'test',
            'new_position': 2,
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    assert result.mlget(['views', 1, 'cards', 2, 'title'],
                        list_ok=True) == 'Test card'
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']


async def test_lovelace_move_card_view(hass, hass_ws_client):
    """Test move_card to view command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/move',
            'card_id': 'test',
            'new_view_id': 'example',
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    assert result.mlget(['views', 0, 'cards', 2, 'title'],
                        list_ok=True) == 'Test card'
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']


async def test_lovelace_move_card_view_position(hass, hass_ws_client):
    """Test move_card to view with position command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/move',
            'card_id': 'test',
            'new_view_id': 'example',
            'new_position': 1,
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    assert result.mlget(['views', 0, 'cards', 1, 'title'],
                        list_ok=True) == 'Test card'
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']


async def test_lovelace_delete_card(hass, hass_ws_client):
    """Test delete_card command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/card/delete',
            'card_id': 'test',
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    cards = result.mlget(['views', 1, 'cards'], list_ok=True)
    assert len(cards) == 2
    assert cards[0]['title'] == 'Example'
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']


async def test_lovelace_get_view(hass, hass_ws_client):
    """Test get_view command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/view/get',
            'view_id': 'example',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert "".join(msg['result'].split()) == "".join('title: Example\n # \
                             Optional unique id for direct\
                             access /lovelace/${id}\nid: example\n # Optional\
                             background (overwrites the global background).\n\
                             background: radial-gradient(crimson, skyblue)\n\
                             # Each view can have a different theme applied.\n\
                             theme: dark-mode\n'.split())


async def test_lovelace_get_view_not_found(hass, hass_ws_client):
    """Test get_card command cannot find card."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/view/get',
            'view_id': 'not_found',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'view_not_found'


async def test_lovelace_update_view(hass, hass_ws_client):
    """Test update_view command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')
    origyaml = yaml.load(TEST_YAML_A)

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=origyaml), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/view/update',
            'view_id': 'example',
            'view_config': 'id: example2\ntitle: New title\n',
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    orig_view = origyaml.mlget(['views', 0], list_ok=True)
    new_view = result.mlget(['views', 0], list_ok=True)
    assert new_view['title'] == 'New title'
    assert new_view['cards'] == orig_view['cards']
    assert 'theme' not in new_view
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']


async def test_lovelace_add_view(hass, hass_ws_client):
    """Test add_view command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/view/add',
            'view_config': 'id: test\ntitle: added\n',
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    assert result.mlget(['views', 2, 'title'],
                        list_ok=True) == 'added'
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']


async def test_lovelace_add_view_position(hass, hass_ws_client):
    """Test add_view command with position."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/view/add',
            'position': 0,
            'view_config': 'id: test\ntitle: added\n',
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    assert result.mlget(['views', 0, 'title'],
                        list_ok=True) == 'added'
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']


async def test_lovelace_move_view_position(hass, hass_ws_client):
    """Test move_view command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/view/move',
            'view_id': 'example',
            'new_position': 1,
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    assert result.mlget(['views', 1, 'title'],
                        list_ok=True) == 'Example'
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']


async def test_lovelace_delete_view(hass, hass_ws_client):
    """Test delete_card command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)
    yaml = YAML(typ='rt')

    with patch('homeassistant.util.ruamel_yaml.load_yaml',
               return_value=yaml.load(TEST_YAML_A)), \
        patch('homeassistant.util.ruamel_yaml.save_yaml') \
            as save_yaml_mock:
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config/view/delete',
            'view_id': 'example',
        })
        msg = await client.receive_json()

    result = save_yaml_mock.call_args_list[0][0][1]
    views = result.get('views', [])
    assert len(views) == 1
    assert views[0]['title'] == 'Second view'
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
