"""Tests for :func:`hass_client.schema_bridge.serialize_schema`.

The serialise path must never let an unserialisable schema propagate — a
``register_service`` / flow push that raised would drop the registration on
main entirely. Any failure has to degrade to ``None`` (main installs the
service with no schema; the sandbox still validates).
"""

from typing import Any

from hass_client import schema_bridge
from hass_client.schema_bridge import serialize_schema
import pytest
import voluptuous as vol


def test_serialize_none_returns_none() -> None:
    """``None`` in, ``None`` out."""
    assert serialize_schema(None) is None


def test_serialize_mapping_schema_renders_fields() -> None:
    """A plain mapping schema serialises to the list-of-fields shape."""
    rendered = serialize_schema(vol.Schema({vol.Required("name"): str}))
    assert isinstance(rendered, list)
    assert rendered[0]["name"] == "name"


def test_serialize_non_mapping_schema_returns_none() -> None:
    """A scalar (non-list result) schema degrades to ``None``."""
    assert serialize_schema(vol.Schema(str)) is None


@pytest.mark.parametrize(
    "raised",
    [ValueError("bad"), TypeError("bad"), RuntimeError("exotic"), KeyError("k")],
    ids=["value-error", "type-error", "runtime-error", "key-error"],
)
def test_serialize_failure_degrades_to_none(
    raised: Exception,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Any serialisation failure (not just ValueError/TypeError) returns None.

    The broad fallback is the point: an exotic custom validator that makes
    ``voluptuous_serialize`` raise something other than ValueError/TypeError
    must NOT propagate and drop the registration.
    """

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise raised

    monkeypatch.setattr(schema_bridge.voluptuous_serialize, "convert", _boom)
    assert serialize_schema(vol.Schema({vol.Required("x"): str})) is None
    assert "did not survive serialisation" in caplog.text
