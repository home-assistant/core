"""Tests for hassfest dependency finder."""

import ast

import pytest

from script.hassfest.dependencies import (
    CORE_INTEGRATIONS,
    ImportCollector,
    _validate_dependencies,
)
from script.hassfest.model import Config

from . import get_integration


@pytest.fixture
def mock_collector():
    """Fixture with import collector that adds all referenced nodes."""
    collector = ImportCollector(None)
    collector.unfiltered_referenced = set()
    collector._add_reference = collector.unfiltered_referenced.add
    return collector


def test_child_import(mock_collector) -> None:
    """Test detecting a child_import reference."""
    mock_collector.visit(
        ast.parse(
            """

from homeassistant.components import child_import
"""
        )
    )
    assert mock_collector.unfiltered_referenced == {"child_import"}


def test_subimport(mock_collector) -> None:
    """Test detecting a subimport reference."""
    mock_collector.visit(
        ast.parse(
            """

from homeassistant.components.subimport.smart_home import EVENT_ALEXA_SMART_HOME
"""
        )
    )
    assert mock_collector.unfiltered_referenced == {"subimport"}


def test_child_import_field(mock_collector) -> None:
    """Test detecting a child_import_field reference."""
    mock_collector.visit(
        ast.parse(
            """

from homeassistant.components.child_import_field import bla
"""
        )
    )
    assert mock_collector.unfiltered_referenced == {"child_import_field"}


def test_renamed_absolute(mock_collector) -> None:
    """Test detecting a renamed_absolute reference."""
    mock_collector.visit(
        ast.parse(
            """

import homeassistant.components.renamed_absolute as hue
"""
        )
    )
    assert mock_collector.unfiltered_referenced == {"renamed_absolute"}


def test_all_imports(mock_collector) -> None:
    """Test all imports together."""
    mock_collector.visit(
        ast.parse(
            """

from homeassistant.components import child_import

from homeassistant.components.subimport.smart_home import EVENT_ALEXA_SMART_HOME

from homeassistant.components.child_import_field import bla

import homeassistant.components.renamed_absolute as hue
"""
        )
    )
    assert mock_collector.unfiltered_referenced == {
        "child_import",
        "subimport",
        "child_import_field",
        "renamed_absolute",
    }


def test_dependency_on_core_integration_rejected(config: Config) -> None:
    """Test that depending on a core integration is rejected."""
    consumer = get_integration("consumer", config)
    consumer.manifest["dependencies"] = ["persistent_notification"]

    integrations = {
        "consumer": consumer,
        "persistent_notification": get_integration("persistent_notification", config),
    }

    _validate_dependencies(integrations)

    assert len(consumer.errors) == 1
    assert (
        "Dependency persistent_notification is a core integration"
        in consumer.errors[0].error
    )


def test_dependency_on_non_core_integration_allowed(config: Config) -> None:
    """Test that depending on a non-core integration is not rejected."""
    consumer = get_integration("consumer", config)
    consumer.manifest["dependencies"] = ["other"]

    integrations = {
        "consumer": consumer,
        "other": get_integration("other", config),
    }

    _validate_dependencies(integrations)

    assert consumer.errors == []


def test_core_integrations_in_sync_with_bootstrap() -> None:
    """Test the duplicated CORE_INTEGRATIONS stays aligned with bootstrap."""
    # Imported here so the rest of the hassfest tests are not slowed down
    # by bootstrap's eager component pre-imports.
    from homeassistant.bootstrap import (  # noqa: PLC0415
        CORE_INTEGRATIONS as bootstrap_core_integrations,
    )

    assert bootstrap_core_integrations == CORE_INTEGRATIONS
