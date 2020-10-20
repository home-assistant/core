"""Test blueprint importing."""
import json
from pathlib import Path

import pytest

from homeassistant.components.blueprint import importer, models
from homeassistant.exceptions import HomeAssistantError

from tests.common import load_fixture


@pytest.fixture(scope="session")
def community_post():
    """Topic JSON with a codeblock marked as auto syntax."""
    return load_fixture("blueprint/community_post.json")


def test_get_community_post_import_url():
    """Test variations of generating import forum url."""
    assert (
        importer._get_community_post_import_url(
            "https://community.home-assistant.io/t/test-topic/123"
        )
        == "https://community.home-assistant.io/t/test-topic/123.json"
    )

    assert (
        importer._get_community_post_import_url(
            "https://community.home-assistant.io/t/test-topic/123/2"
        )
        == "https://community.home-assistant.io/t/test-topic/123.json"
    )


def test_get_github_import_url():
    """Test getting github import url."""
    assert (
        importer._get_github_import_url(
            "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml"
        )
        == "https://raw.githubusercontent.com/balloob/home-assistant-config/main/blueprints/automation/motion_light.yaml"
    )

    assert (
        importer._get_github_import_url(
            "https://raw.githubusercontent.com/balloob/home-assistant-config/main/blueprints/automation/motion_light.yaml"
        )
        == "https://raw.githubusercontent.com/balloob/home-assistant-config/main/blueprints/automation/motion_light.yaml"
    )


def test_extract_blueprint_from_community_topic(community_post):
    """Test extracting blueprint."""
    blueprint = importer._extract_blueprint_from_community_topic(
        json.loads(community_post)
    )
    assert isinstance(blueprint, models.Blueprint)
    assert blueprint.domain == "automation"
    assert blueprint.placeholders == {"service_to_call", "trigger_event"}


def test_extract_blueprint_from_community_topic_invalid_yaml():
    """Test extracting blueprint with invalid YAML."""
    with pytest.raises(HomeAssistantError):
        importer._extract_blueprint_from_community_topic(
            {
                "post_stream": {
                    "posts": [
                        {"cooked": '<code class="lang-yaml">invalid: yaml: 2</code>'}
                    ]
                }
            }
        )


def test__extract_blueprint_from_community_topic_wrong_lang():
    """Test extracting blueprint with invalid YAML."""
    assert (
        importer._extract_blueprint_from_community_topic(
            {
                "post_stream": {
                    "posts": [
                        {"cooked": '<code class="lang-php">invalid yaml + 2</code>'}
                    ]
                }
            }
        )
        is None
    )


async def test_fetch_blueprint_from_community_url(hass, aioclient_mock, community_post):
    """Test fetching blueprint from url."""
    aioclient_mock.get(
        "https://community.home-assistant.io/t/test-topic/123.json", text=community_post
    )
    blueprint = await importer.fetch_blueprint_from_url(
        hass, "https://community.home-assistant.io/t/test-topic/123/2"
    )
    assert isinstance(blueprint, models.Blueprint)
    assert blueprint.domain == "automation"
    assert blueprint.placeholders == {"service_to_call", "trigger_event"}


async def test_fetch_blueprint_from_github_url(hass, aioclient_mock):
    """Test fetching blueprint from url."""
    aioclient_mock.get(
        "https://raw.githubusercontent.com/balloob/home-assistant-config/main/blueprints/automation/motion_light.yaml",
        text=Path(
            hass.config.path("blueprints/automation/test_event_service.yaml")
        ).read_text(),
    )

    for url in (
        "https://raw.githubusercontent.com/balloob/home-assistant-config/main/blueprints/automation/motion_light.yaml",
        "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
    ):
        blueprint = await importer.fetch_blueprint_from_url(hass, url)
        assert isinstance(blueprint, models.Blueprint), url
        assert blueprint.domain == "automation", url
        assert blueprint.placeholders == {"service_to_call", "trigger_event"}, url
