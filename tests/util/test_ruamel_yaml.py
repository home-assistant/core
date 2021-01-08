"""Test Home Assistant ruamel.yaml loader."""
import os
from tempfile import mkdtemp

import pytest
from ruamel.yaml import YAML

from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.ruamel_yaml as util_yaml

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

TMP_DIR = None


def setup():
    """Set up for tests."""
    global TMP_DIR
    TMP_DIR = mkdtemp()


def teardown():
    """Clean up after tests."""
    for fname in os.listdir(TMP_DIR):
        os.remove(os.path.join(TMP_DIR, fname))
    os.rmdir(TMP_DIR)


def _path_for(leaf_name):
    return os.path.join(TMP_DIR, f"{leaf_name}.yaml")


def test_save_and_load():
    """Test saving and loading back."""
    yaml = YAML(typ="rt")
    fname = _path_for("test1")
    open(fname, "w+").close()
    util_yaml.save_yaml(fname, yaml.load(TEST_YAML_A))
    data = util_yaml.load_yaml(fname, True)
    assert data == yaml.load(TEST_YAML_A)


def test_overwrite_and_reload():
    """Test that we can overwrite an existing file and read back."""
    yaml = YAML(typ="rt")
    fname = _path_for("test2")
    open(fname, "w+").close()
    util_yaml.save_yaml(fname, yaml.load(TEST_YAML_A))
    util_yaml.save_yaml(fname, yaml.load(TEST_YAML_B))
    data = util_yaml.load_yaml(fname, True)
    assert data == yaml.load(TEST_YAML_B)


def test_load_bad_data():
    """Test error from trying to load unserialisable data."""
    fname = _path_for("test3")
    with open(fname, "w") as fh:
        fh.write(TEST_BAD_YAML)
    with pytest.raises(HomeAssistantError):
        util_yaml.load_yaml(fname, True)
