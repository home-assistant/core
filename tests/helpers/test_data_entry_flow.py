"""Tests for the data entry flow helper."""

from unittest.mock import Mock

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.helpers.data_entry_flow import _BaseFlowManagerView


def test_prepare_result_json_includes_visible() -> None:
    """Test the serialized data_schema carries visible conditions."""
    condition = {"field": "use_tls", "value": True}
    schema = vol.Schema(
        {
            vol.Required("use_tls", default=True): bool,
            data_entry_flow.Required("cert_path", visible=condition): str,
        }
    )
    view = _BaseFlowManagerView(Mock())
    result = data_entry_flow.FlowResult(
        type=data_entry_flow.FlowResultType.FORM,
        flow_id="1234",
        handler="test",
        step_id="init",
        data_schema=schema,
    )

    data = view._prepare_result_json(result)

    fields = {field["name"]: field for field in data["data_schema"]}
    assert fields["cert_path"]["visible"] == condition
    assert "visible" not in fields["use_tls"]
