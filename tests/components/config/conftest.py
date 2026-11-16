"""Test fixtures for the config integration."""

from collections.abc import Generator, Iterable
from contextlib import contextmanager
from copy import deepcopy
import json
import logging
from os.path import basename
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import raise_contains_mocks

from homeassistant.core import HomeAssistant
from homeassistant.helpers import translation
from homeassistant.loader import Integration

_LOGGER = logging.getLogger(__name__)


@contextmanager
def mock_config_store(data: dict[str, Any] | None = None) -> Generator[dict[str, Any]]:
    """Mock config yaml store.

    Data is a dict {'key': {'version': version, 'data': data}}

    Written data will be converted to JSON to ensure JSON parsing works.
    """
    if data is None:
        data = {}

    def mock_read(path):
        """Mock version of load."""
        file_name = basename(path)
        _LOGGER.info("Reading data from %s: %s", file_name, data.get(file_name))
        return deepcopy(data.get(file_name))

    def mock_write(path, data_to_write):
        """Mock version of write."""
        file_name = basename(path)
        _LOGGER.info("Writing data to %s: %s", file_name, data_to_write)
        raise_contains_mocks(data_to_write)
        # To ensure that the data can be serialized
        data[file_name] = json.loads(json.dumps(data_to_write))

    async def mock_async_hass_config_yaml(hass: HomeAssistant) -> dict:
        """Mock version of async_hass_config_yaml."""
        result = {}
        # Return a configuration.yaml with "automation" mapped to the contents of
        # automations.yaml and so on.
        for key, value in data.items():
            result[key.partition(".")[0][0:-1]] = deepcopy(value)
        _LOGGER.info("Reading data from configuration.yaml: %s", result)
        return result

    with (
        patch(
            "homeassistant.components.config.view._read",
            side_effect=mock_read,
            autospec=True,
        ),
        patch(
            "homeassistant.components.config.view._write",
            side_effect=mock_write,
            autospec=True,
        ),
        patch(
            "homeassistant.config.async_hass_config_yaml",
            side_effect=mock_async_hass_config_yaml,
            autospec=True,
        ),
    ):
        yield data


@pytest.fixture
def hass_config_store() -> Generator[dict[str, Any]]:
    """Fixture to mock config yaml store."""
    with mock_config_store() as stored_data:
        yield stored_data


@pytest.fixture
def mock_translations(
    hass: HomeAssistant, request: pytest.FixtureRequest
) -> Generator[None]:
    """Provide strings.json-shaped translations for mocked integrations."""
    strings_by_domain: dict[str, dict[str, Any]] = getattr(request, "param", {})
    cache = translation._async_get_translations_cache(hass)
    domains = set(strings_by_domain)
    cache.async_invalidate(domains)
    real_get_strings = translation._async_get_component_strings

    async def _get_component_strings(
        hass_arg: HomeAssistant,
        languages: Iterable[str],
        components: set[str],
        integrations: dict[str, Integration],
    ) -> dict[str, dict[str, Any]]:
        result = await real_get_strings(hass_arg, languages, components, integrations)
        for lang in languages:
            lang_strings = result.setdefault(lang, {})
            for domain in components.intersection(domains):
                lang_strings[domain] = deepcopy(strings_by_domain[domain])
        return result

    with patch(
        "homeassistant.helpers.translation._async_get_component_strings",
        side_effect=_get_component_strings,
    ):
        yield
    cache.async_invalidate(domains)
