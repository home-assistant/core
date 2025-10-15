"""Test the AWS S3 config flow model."""

from itertools import combinations

import pytest

from homeassistant.components.aws_s3.config_model import S3ConfigModel
from homeassistant.components.aws_s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
)

from .const import USER_INPUT


def test_init() -> None:
    """Test initialization of S3ConfigModel and its default state."""
    model = S3ConfigModel()
    assert len(model) == 4
    assert model.keys() == {
        CONF_BUCKET,
        CONF_ENDPOINT_URL,
        CONF_ACCESS_KEY_ID,
        CONF_SECRET_ACCESS_KEY,
    }
    assert all(x is None for x in model.values())
    assert model.has_errors(set(model.keys())) is False


@pytest.mark.parametrize(
    ("data"),
    [
        USER_INPUT,
    ],
)
def test_from_dict(data: dict[str, str]) -> None:
    """Test loading values from a dictionary into the model."""
    model = S3ConfigModel()
    model.from_dict(data)
    for k, v in data.items():
        assert model[k] == v


@pytest.mark.parametrize(
    ("data"),
    [
        USER_INPUT,
    ],
)
def test_as_dict_only(data: dict[str, str]) -> None:
    """Test as_dict returns only requested keys and handles invalid keys."""
    model = S3ConfigModel()
    model.from_dict(data)
    for combo_len in range(1, len(data) + 1):
        for combo in combinations(data.keys(), combo_len):
            test = model.as_dict(combo)
            assert len(test) == len(combo)
            for k, v in test.items():
                assert data[k] == v
    test = model.as_dict(set({}))
    assert len(test) == 0
    test = model.as_dict({CONF_BUCKET, "Invalid"})
    assert len(test) == 1
    assert CONF_BUCKET in test
    assert test[CONF_BUCKET] == data[CONF_BUCKET]


@pytest.mark.parametrize(
    ("data"),
    [
        USER_INPUT,
    ],
)
def test_as_dict(data: dict[str, str]) -> None:
    """Test as_dict returns all keys by default and with None argument."""
    model = S3ConfigModel()
    model.from_dict(data)
    test = model.as_dict()
    assert len(test) == len(data)
    for k, v in test.items():
        assert data[k] == v
    test = model.as_dict(None)
    assert len(test) == len(data)
    for k, v in test.items():
        assert data[k] == v


def test_del_item() -> None:
    """Test deleting an item from the model removes the key."""
    model = S3ConfigModel()
    keys_before = set(model.keys())
    del model[CONF_BUCKET]
    keys_after = set(model.keys())
    assert keys_before - keys_after == {CONF_BUCKET}
