"""Tests for hassfest services."""

import probatio
import pytest

from homeassistant.util.yaml.loader import parse_yaml
from script.hassfest import services


@pytest.mark.parametrize(
    "services_yaml",
    [
        pytest.param(
            """
            set_timer:
              fields:
                end_of_track:
                  selector:
                    constant:
                      value: true
                duration:
                  visible:
                    field: end_of_track
                    operator: not_exists
                  selector:
                    duration:
            """,
            id="field",
        ),
        pytest.param(
            """
            set_timer:
              fields:
                mode:
                  selector:
                    select:
                      options:
                        - duration
                        - end_of_track
                advanced:
                  visible:
                    - field: mode
                      value: duration
                  fields:
                    duration:
                      selector:
                        duration:
                    fade:
                      visible:
                        field: duration
                        operator: exists
                      selector:
                        boolean:
            """,
            id="section",
        ),
        pytest.param(
            """
            set_timer:
              fields:
                mode:
                  visible: false
                  selector:
                    text:
            """,
            id="boolean",
        ),
    ],
)
def test_valid_visible(services_yaml: str) -> None:
    """Test valid visible conditions."""
    services.CORE_INTEGRATION_SERVICES_SCHEMA(parse_yaml(services_yaml))


@pytest.mark.parametrize(
    "services_yaml",
    [
        pytest.param(
            """
            set_timer:
              fields:
                duration:
                  visible:
                    field: mode
                    value: duration
                  selector:
                    duration:
            """,
            id="unknown_field",
        ),
        pytest.param(
            """
            set_timer:
              fields:
                duration:
                  visible:
                    field: duration
                    operator: exists
                  selector:
                    duration:
            """,
            id="itself",
        ),
        pytest.param(
            """
            set_timer:
              fields:
                advanced:
                  visible:
                    field: duration
                    operator: exists
                  fields:
                    duration:
                      selector:
                        duration:
            """,
            id="section_own_field",
        ),
        pytest.param(
            """
            set_timer:
              fields:
                duration:
                  visible:
                    field: mode
                    operator: greater_than
                    value: 1
                  selector:
                    duration:
            """,
            id="unknown_operator",
        ),
    ],
)
def test_invalid_visible(services_yaml: str) -> None:
    """Test invalid visible conditions are rejected."""
    with pytest.raises(probatio.Invalid):
        services.CORE_INTEGRATION_SERVICES_SCHEMA(parse_yaml(services_yaml))
