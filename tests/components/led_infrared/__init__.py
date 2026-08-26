"""Tests for the LED Infrared integration."""

from infrared_protocols.codes.generic.led import (
    Generic13KeyCode,
    Generic24KeyCode,
    Generic40KeyCode,
    Generic44KeyCode,
)

type LEDIrKeyCode = (
    Generic13KeyCode | Generic24KeyCode | Generic40KeyCode | Generic44KeyCode
)

EVENT_ENTITY_ID = "event.led_infrared_via_test_ir_emitter_received_command"
LIGHT_ENTITY_ID = "light.led_infrared_via_test_ir_emitter"
