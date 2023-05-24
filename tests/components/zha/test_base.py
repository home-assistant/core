"""Test ZHA base cluster handlers module."""

from homeassistant.components.zha.core.cluster_handlers import parse_and_log_command

from tests.components.zha.test_cluster_handlers import (  # noqa: F401
    endpoint,
    poll_control_ch,
    zigpy_coordinator_device,
)


def test_parse_and_log_command(poll_control_ch):  # noqa: F811
    """Test that `parse_and_log_command` correctly parses a known command."""
    assert parse_and_log_command(poll_control_ch, 0x00, 0x01, []) == "fast_poll_stop"


def test_parse_and_log_command_unknown(poll_control_ch):  # noqa: F811
    """Test that `parse_and_log_command` correctly parses an unknown command."""
    assert parse_and_log_command(poll_control_ch, 0x00, 0xAB, []) == "0xAB"
