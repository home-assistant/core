"""Tests for the Mistral API helpers."""

import datetime

from mistralai.client.types import UNSET

from homeassistant.components.mistral_ai.api import is_unset, model_status_from_list


class _Model:
    def __init__(self, model_id, deprecation=UNSET, replacement=UNSET) -> None:
        self.id = model_id
        self.deprecation = deprecation
        self.deprecation_replacement_model = replacement


def test_is_unset() -> None:
    """UNSET sentinel detection."""
    assert is_unset(UNSET)
    assert not is_unset(None)
    assert not is_unset("x")


def test_model_status_active() -> None:
    """Active model with no deprecation."""
    models = [_Model("mistral-small-latest", deprecation=UNSET, replacement=UNSET)]
    assert model_status_from_list(models, "mistral-small-latest") == {
        "id": "mistral-small-latest",
        "status": "active",
        "deprecation": None,
        "deprecation_replacement_model": None,
    }


def test_model_status_deprecated() -> None:
    """Deprecated model with a replacement."""
    dep = datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)
    models = [
        _Model("mistral-old", deprecation=dep, replacement="mistral-small-latest")
    ]
    assert model_status_from_list(models, "mistral-old") == {
        "id": "mistral-old",
        "status": "deprecated",
        "deprecation": dep.isoformat(),
        "deprecation_replacement_model": "mistral-small-latest",
    }


def test_model_status_deprecated_no_replacement() -> None:
    """Deprecated model without replacement."""
    dep = datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)
    models = [_Model("mistral-old", deprecation=dep, replacement=None)]
    assert model_status_from_list(models, "mistral-old")["status"] == "deprecated"
    assert (
        model_status_from_list(models, "mistral-old")["deprecation_replacement_model"]
        is None
    )


def test_model_status_unknown() -> None:
    """Model absent from the list."""
    models = [_Model("mistral-small-latest")]
    assert model_status_from_list(models, "does-not-exist") == {
        "id": "does-not-exist",
        "status": "unknown",
    }
