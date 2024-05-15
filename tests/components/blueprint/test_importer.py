"""Test blueprint importing."""

import json
from pathlib import Path

import pytest

from homeassistant.components.blueprint import importer
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(scope="module")
def community_post():
    """Topic JSON with a codeblock marked as auto syntax."""
    return load_fixture("blueprint/community_post.json")


def test_get_community_post_import_url() -> None:
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


def test_get_github_import_url() -> None:
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


def test_extract_blueprint_from_community_topic(community_post, snapshot) -> None:
    """Test extracting blueprint."""
    imported_blueprint = importer._extract_blueprint_from_community_topic(
        "http://example.com", json.loads(community_post)
    )
    assert imported_blueprint is not None
    assert imported_blueprint.blueprint.domain == "automation"
    assert imported_blueprint.blueprint.inputs == snapshot


def test_extract_blueprint_from_community_topic_invalid_yaml() -> None:
    """Test extracting blueprint with invalid YAML."""
    with pytest.raises(HomeAssistantError):
        importer._extract_blueprint_from_community_topic(
            "http://example.com",
            {
                "post_stream": {
                    "posts": [
                        {"cooked": '<code class="lang-yaml">invalid: yaml: 2</code>'}
                    ]
                }
            },
        )


def test_extract_blueprint_from_community_topic_wrong_lang() -> None:
    """Test extracting blueprint with invalid YAML."""
    with pytest.raises(importer.HomeAssistantError):
        assert importer._extract_blueprint_from_community_topic(
            "http://example.com",
            {
                "post_stream": {
                    "posts": [
                        {"cooked": '<code class="lang-php">invalid yaml + 2</code>'}
                    ]
                }
            },
        )


async def test_fetch_blueprint_from_community_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, community_post, snapshot
) -> None:
    """Test fetching blueprint from url."""
    aioclient_mock.get(
        "https://community.home-assistant.io/t/test-topic/123.json", text=community_post
    )
    imported_blueprint = await importer.fetch_blueprint_from_url(
        hass, "https://community.home-assistant.io/t/test-topic/123/2"
    )
    assert isinstance(imported_blueprint, importer.ImportedBlueprint)
    assert imported_blueprint.blueprint.domain == "automation"
    assert imported_blueprint.blueprint.inputs == snapshot
    assert (
        imported_blueprint.suggested_filename
        == "frenck/zha-ikea-five-button-remote-for-lights"
    )
    assert (
        imported_blueprint.blueprint.metadata["source_url"]
        == "https://community.home-assistant.io/t/test-topic/123/2"
    )
    assert "gt;" not in imported_blueprint.raw_data


@pytest.mark.parametrize(
    "url",
    [
        "https://raw.githubusercontent.com/balloob/home-assistant-config/main/blueprints/automation/motion_light.yaml",
        "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
    ],
)
async def test_fetch_blueprint_from_github_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, url: str
) -> None:
    """Test fetching blueprint from url."""
    aioclient_mock.get(
        "https://raw.githubusercontent.com/balloob/home-assistant-config/main/blueprints/automation/motion_light.yaml",
        text=Path(
            hass.config.path("blueprints/automation/test_event_service.yaml")
        ).read_text(),
    )

    imported_blueprint = await importer.fetch_blueprint_from_url(hass, url)
    assert isinstance(imported_blueprint, importer.ImportedBlueprint)
    assert imported_blueprint.blueprint.domain == "automation"
    assert imported_blueprint.blueprint.inputs == {
        "service_to_call": None,
        "trigger_event": {"selector": {"text": {}}},
        "a_number": {"selector": {"number": {"mode": "box", "step": 1.0}}},
    }
    assert imported_blueprint.suggested_filename == "balloob/motion_light"
    assert imported_blueprint.blueprint.metadata["source_url"] == url


async def test_fetch_blueprint_from_github_gist_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, snapshot
) -> None:
    """Test fetching blueprint from url."""
    aioclient_mock.get(
        "https://api.github.com/gists/e717ce85dd0d2f1bdcdfc884ea25a344",
        text=load_fixture("blueprint/github_gist.json"),
    )

    url = "https://gist.github.com/balloob/e717ce85dd0d2f1bdcdfc884ea25a344"
    imported_blueprint = await importer.fetch_blueprint_from_url(hass, url)
    assert isinstance(imported_blueprint, importer.ImportedBlueprint)
    assert imported_blueprint.blueprint.domain == "automation"
    assert imported_blueprint.blueprint.inputs == snapshot
    assert imported_blueprint.suggested_filename == "balloob/motion_light"
    assert imported_blueprint.blueprint.metadata["source_url"] == url


async def test_fetch_blueprint_from_website_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test fetching blueprint from url."""
    aioclient_mock.get(
        "https://www.home-assistant.io/blueprints/awesome.yaml",
        text=Path(
            hass.config.path("blueprints/automation/test_event_service.yaml")
        ).read_text(),
    )

    url = "https://www.home-assistant.io/blueprints/awesome.yaml"
    imported_blueprint = await importer.fetch_blueprint_from_url(hass, url)
    assert isinstance(imported_blueprint, importer.ImportedBlueprint)
    assert imported_blueprint.blueprint.domain == "automation"
    assert imported_blueprint.suggested_filename == "homeassistant/awesome"
    assert imported_blueprint.blueprint.metadata["source_url"] == url


async def test_fetch_blueprint_from_unsupported_url(hass: HomeAssistant) -> None:
    """Test fetching blueprint from an unsupported URL."""
    url = "https://example.com/unsupported.yaml"

    with pytest.raises(HomeAssistantError, match=r"^Unsupported URL$"):
        await importer.fetch_blueprint_from_url(hass, url)
