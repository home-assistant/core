"""Useful functions for the IHC component."""

import time


def pulse(ihc_controller, ihc_id: int):
    """Send a short on/off pulse to an IHC controller resource."""
    ihc_controller.set_runtime_value_bool(ihc_id, True)
    time.sleep(0.1)
    ihc_controller.set_runtime_value_bool(ihc_id, False)
