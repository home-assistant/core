"""Useful functions for the IHC component."""

import asyncio

from homeassistant.core import callback


async def async_pulse(hass, ihc_controller, ihc_id: int):
    """Send a short on/off pulse to an IHC controller resource."""
    await async_set_bool(hass, ihc_controller, ihc_id, True)
    await asyncio.sleep(0.1)
    await async_set_bool(hass, ihc_controller, ihc_id, False)


@callback
def async_set_bool(hass, ihc_controller, ihc_id: int, value: bool):
    """Set a bool value on an IHC controller resource."""
    return hass.async_add_executor_job(
        ihc_controller.set_runtime_value_bool, ihc_id, value
    )


@callback
def async_set_int(hass, ihc_controller, ihc_id: int, value: int):
    """Set a int value on an IHC controller resource."""
    return hass.async_add_executor_job(
        ihc_controller.set_runtime_value_int, ihc_id, value
    )


@callback
def async_set_float(hass, ihc_controller, ihc_id: int, value: float):
    """Set a float value on an IHC controller resource."""
    return hass.async_add_executor_job(
        ihc_controller.set_runtime_value_float, ihc_id, value
    )
