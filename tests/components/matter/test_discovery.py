"""Test Matter discovery helpers."""

from unittest.mock import MagicMock

from chip.clusters import Objects as clusters
from chip.clusters.ClusterObjects import ClusterAttributeDescriptor, NullValue
import pytest

from homeassistant.components.matter.discovery import _resolve_cluster_revision
from homeassistant.components.matter.models import MatterDiscoverySchema
from homeassistant.const import Platform


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
        (None, None, 5, True, 0),
        (7, None, 6, False, 1),
        (7, None, 7, True, 1),
        (None, 6, 7, False, 1),
        (None, 6, 6, True, 1),
        (2, 6, 1, False, 1),
        (2, 6, 7, False, 1),
        (2, 6, 4, True, 1),
        (7, None, None, True, 1),
        (7, None, NullValue, True, 1),
    ],
    ids=[
        "no bounds",
        "min unmet",
        "min met",
        "max exceeded",
        "max met",
        "below range",
        "above range",
        "within range",
        "unreadable revision (None)",
        "unreadable revision (NullValue)",
    ],
)
def test_resolve_cluster_revision(
    cluster_revision_min: int | None,
    cluster_revision_max: int | None,
    raw_cluster_revision: int | None,
    expected: bool,
    expected_call_count: int,
) -> None:
    """Test _resolve_cluster_revision matches schema bounds against ClusterRevision."""
    endpoint = MagicMock()
    endpoint.get_attribute_value.return_value = raw_cluster_revision
    schema = _make_schema(cluster_revision_min, cluster_revision_max)
    primary_attribute: type[ClusterAttributeDescriptor] = schema.required_attributes[0]

    assert _resolve_cluster_revision(endpoint, primary_attribute, schema) is expected
    assert endpoint.get_attribute_value.call_count == expected_call_count
