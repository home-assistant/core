"""Test the AWS S3 config flow model."""

from homeassistant.components.aws_s3.config_model import S3ConfigModel
from homeassistant.components.aws_s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
)


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
