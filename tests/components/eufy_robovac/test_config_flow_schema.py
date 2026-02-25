"""Tests for Eufy RoboVac config flow schema."""

import pytest
import voluptuous as vol

from homeassistant.components.eufy_robovac.config_flow import USER_STEP_DATA_SCHEMA


def test_user_schema_accepts_t2253() -> None:
    """The user schema should accept T2253 inputs."""
    data = USER_STEP_DATA_SCHEMA(
        {
            "name": "Hall Vacuum",
            "model": "T2253",
            "host": "192.168.1.50",
            "id": "abc123",
            "local_key": "local_key_123",
        }
    )

    assert data["model"] == "T2253"
    assert data["protocol_version"] == "3.3"


def test_user_schema_rejects_unknown_model() -> None:
    """Unknown model codes should be rejected by schema."""
    with pytest.raises(vol.Invalid):
        USER_STEP_DATA_SCHEMA(
            {
                "name": "Hall Vacuum",
                "model": "UNKNOWN",
                "host": "192.168.1.50",
                "id": "abc123",
                "local_key": "local_key_123",
            }
        )
