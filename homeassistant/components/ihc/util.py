"""Utility methods for IHC"""

import time

def pulse(ihc_controller, ihc_id: int):
    ihc_controller.set_runtime_value_bool(ihc_id, True)
    time.sleep(0.1)
    ihc_controller.set_runtime_value_bool(ihc_id, False)