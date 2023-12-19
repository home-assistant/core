"""Test for the alarm control panel const module."""

import pytest

from homeassistant.components.alarm_control_panel import const

from tests.common import validate_deprecated_constant
from tests.testing_config.custom_components.test_constant_deprecation.alarm_control_panel import (
    import_deprecated_code_format,
    import_deprecated_entity_feature,
)


@pytest.mark.parametrize(
    "code_format",
    list(const.CodeFormat),
)
def test_deprecated_constant_code_format(
    caplog: pytest.LogCaptureFixture,
    code_format: const.CodeFormat,
) -> None:
    """Test deprecated binary sensor device classes."""
    import_deprecated_code_format(code_format, const)
    validate_deprecated_constant(caplog, const, code_format, "FORMAT_", "2025.1")


@pytest.mark.parametrize(
    "entity_feature",
    list(const.AlarmControlPanelEntityFeature),
)
def test_deprecated_constant_entity_feature(
    caplog: pytest.LogCaptureFixture,
    entity_feature: const.AlarmControlPanelEntityFeature,
) -> None:
    """Test deprecated binary sensor device classes."""
    import_deprecated_entity_feature(entity_feature, const)
    validate_deprecated_constant(
        caplog, const, entity_feature, "SUPPORT_ALARM_", "2025.1"
    )
