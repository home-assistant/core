"""Test Matter discovery helpers."""

from unittest.mock import MagicMock

from chip.clusters import Objects as clusters
from chip.clusters.ClusterObjects import ClusterAttributeDescriptor, NullValue
import pytest

from homeassistant.components.matter import discovery
from homeassistant.components.matter.discovery import (
    _matches_cluster_revision,
    async_discover_entities,
)
from homeassistant.components.matter.models import MatterDiscoverySchema
from homeassistant.const import Platform

from .common import create_node_from_fixture


def _make_schema(
    cluster_revision_min: int | None, cluster_revision_max: int | None
) -> MatterDiscoverySchema:
    """Return a minimal MatterDiscoverySchema for cluster_revision filtering tests."""
    return MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MagicMock(),
        entity_class=MagicMock(),
        required_attributes=(
            clusters.Thermostat.Attributes.LocalTemperatureCalibration,
        ),
        cluster_revision_min=cluster_revision_min,
        cluster_revision_max=cluster_revision_max,
    )


@pytest.mark.parametrize(
    (
        "cluster_revision_min",
        "cluster_revision_max",
        "raw_cluster_revision",
        "expected",
        "expected_call_count",
    ),
    [
        pytest.param(None, None, 5, True, 0, id="no bounds"),
        pytest.param(7, None, 6, False, 1, id="min unmet"),
        pytest.param(7, None, 7, True, 1, id="min met"),
        pytest.param(None, 6, 7, False, 1, id="max exceeded"),
        pytest.param(None, 6, 6, True, 1, id="max met"),
        pytest.param(2, 6, 1, False, 1, id="below range"),
        pytest.param(2, 6, 7, False, 1, id="above range"),
        pytest.param(2, 6, 4, True, 1, id="within range"),
        pytest.param(7, None, None, True, 1, id="unreadable revision (None)"),
        pytest.param(7, None, NullValue, True, 1, id="unreadable revision (NullValue)"),
        pytest.param(
            7,
            None,
            0,
            True,
            1,
            id="unreadable revision (0, unpopulated uint16 default)",
        ),
    ],
)
def test_matches_cluster_revision(
    cluster_revision_min: int | None,
    cluster_revision_max: int | None,
    raw_cluster_revision: int | None,
    expected: bool,
    expected_call_count: int,
) -> None:
    """Test _matches_cluster_revision matches schema bounds against ClusterRevision."""
    endpoint = MagicMock()
    endpoint.get_attribute_value.return_value = raw_cluster_revision
    schema = _make_schema(cluster_revision_min, cluster_revision_max)
    primary_attribute: type[ClusterAttributeDescriptor] = schema.required_attributes[0]

    assert _matches_cluster_revision(endpoint, primary_attribute, schema) is expected
    assert endpoint.get_attribute_value.call_count == expected_call_count


@pytest.mark.parametrize(
    ("cluster_revision", "expected_discovered"),
    [
        pytest.param(6, True, id="within range"),
        pytest.param(7, False, id="above range"),
        pytest.param(0, True, id="unreadable revision (0)"),
    ],
)
def test_async_discover_entities_filters_by_cluster_revision(
    monkeypatch: pytest.MonkeyPatch,
    cluster_revision: int,
    expected_discovered: bool,
) -> None:
    """Test async_discover_entities honors cluster_revision_min/cluster_revision_max."""
    schema = _make_schema(cluster_revision_min=None, cluster_revision_max=6)
    monkeypatch.setattr(discovery, "DISCOVERY_SCHEMAS", {Platform.SENSOR: [schema]})
    node = create_node_from_fixture(
        "mock_thermostat", override_attributes={"1/513/65533": cluster_revision}
    )
    endpoint = node.endpoints[1]

    assert bool(list(async_discover_entities(endpoint))) is expected_discovered
