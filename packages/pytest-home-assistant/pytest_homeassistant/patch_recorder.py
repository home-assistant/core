"""Patch recorder related functions."""

from contextlib import contextmanager
import sys

# Patch recorder util session scope
from homeassistant.helpers import recorder as recorder_helper

# Make sure homeassistant.components.recorder.util is not already imported
assert "homeassistant.components.recorder.util" not in sys.modules

real_session_scope = recorder_helper.session_scope


@contextmanager
def _session_scope_wrapper(*args, **kwargs):
    """Provide a patchable recorder session scope."""
    with real_session_scope(*args, **kwargs) as ses:
        yield ses


recorder_helper.session_scope = _session_scope_wrapper
