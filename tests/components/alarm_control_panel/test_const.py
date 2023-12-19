"""Test for the alarm control panel const module."""
import logging

import pytest

from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature,
    CodeFormat,
)

from tests.testing_config.custom_components.test_constant_deprecation.alarm_control_panel import (
    import_deprecated_code_format,
    import_deprecated_entity_feature,
)


@pytest.mark.parametrize(
    "code_format",
    list(CodeFormat),
)
def test_deprecated_constant_code_format(
    caplog: pytest.LogCaptureFixture,
    code_format: CodeFormat,
) -> None:
    """Test deprecated binary sensor device classes."""
    import_deprecated_code_format(code_format)

    assert (
        "homeassistant.components.alarm_control_panel.const",
        logging.WARNING,
        (
            f"FORMAT_{code_format.name} was used from test_constant_deprecation,"
            " this is a deprecated constant which will be removed in HA Core 2025.1. "
            f"Use CodeFormat.{code_format.name} instead, please report "
            "it to the author of the 'test_constant_deprecation' custom integration"
        ),
    ) in caplog.record_tuples


@pytest.mark.parametrize(
    "entity_feature",
    list(AlarmControlPanelEntityFeature),
)
def test_deprecated_constant_entity_feature(
    caplog: pytest.LogCaptureFixture,
    entity_feature: AlarmControlPanelEntityFeature,
) -> None:
    """Test deprecated binary sensor device classes."""
    import_deprecated_entity_feature(entity_feature)

    assert (
        "homeassistant.components.alarm_control_panel.const",
        logging.WARNING,
        (
            f"SUPPORT_ALARM_{entity_feature.name} was used from test_constant_deprecation,"
            " this is a deprecated constant which will be removed in HA Core 2025.1. "
            f"Use AlarmControlPanelEntityFeature.{entity_feature.name} instead, please report "
            "it to the author of the 'test_constant_deprecation' custom integration"
        ),
    ) in caplog.record_tuples
