"""Test deprecated alarm control panel constants."""
from homeassistant.components import alarm_control_panel
from homeassistant.components.alarm_control_panel import const


def import_deprecated_code_format(code_format: const.CodeFormat):
    """Import deprecated code format constant."""
    assert getattr(alarm_control_panel, f"FORMAT_{code_format.name}") == code_format


def import_deprecated_code_format_const(code_format: const.CodeFormat):
    """Import deprecated code format constant."""
    assert getattr(const, f"FORMAT_{code_format.name}") == code_format


def import_deprecated_entity_feature(
    entity_feature: const.AlarmControlPanelEntityFeature
):
    """Import deprecated entity feature constant."""
    assert (
        getattr(alarm_control_panel, f"SUPPORT_ALARM_{entity_feature.name}")
        == entity_feature
    )


def import_deprecated_entity_feature_const(
    entity_feature: const.AlarmControlPanelEntityFeature
):
    """Import deprecated entity feature constant."""
    assert getattr(const, f"SUPPORT_ALARM_{entity_feature.name}") == entity_feature
