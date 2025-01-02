"""Test repair flows."""

import pytest

from homeassistant.components.assist_pipeline.repair_flows import (
    AssistInProgressDeprecatedRepairFlow,
)


@pytest.mark.parametrize(
    "data", [None, {}, {"entity_id": "blah", "entity_uuid": "12345"}]
)
def test_assist_in_progress_deprecated_flow_requires_data(data: dict | None) -> None:
    """Test AssistInProgressDeprecatedRepairFlow requires data."""

    with pytest.raises(ValueError):
        AssistInProgressDeprecatedRepairFlow(data)
