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
            record:
              fields:
                snapshot:
                  selector:
                    constant:
                      value: true
                duration:
                  visible:
                    field: snapshot
                    operator: not_exists
                  selector:
                    duration:
            """,
            id="field",
        ),
        pytest.param(
            """
            record:
              fields:
                mode:
                  selector:
                    select:
                      options:
                        - clip
                        - snapshot
                advanced:
                  visible:
                    - field: mode
                      value: clip
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
            record:
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
            record:
              fields:
                duration:
                  visible:
                    field: mode
                    value: clip
                  selector:
                    duration:
            """,
            id="unknown_field",
        ),
        pytest.param(
            """
            record:
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
            record:
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
            record:
              fields:
                options:
                  visible:
                    field: options
                    operator: exists
                  fields:
                    options:
                      selector:
                        text:
            """,
            id="section_and_field_with_the_same_name",
        ),
        pytest.param(
            """
            record:
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
