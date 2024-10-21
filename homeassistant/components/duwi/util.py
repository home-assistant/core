"""Utility methods for the Duwi Smart Hub integration"""

import asyncio
import json
import logging
from typing import Callable, Optional

from duwi_smarthome_sdk.const.status import Code

from homeassistant.components.persistent_notification import (
    async_create as async_create_notification,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def trans_duwi_state_to_ha_state(
    hass: HomeAssistant, instance_id: str, message: str
):
    """
    Synchronize the entity's state in Home Assistant based on the received message.

    This asynchronous function analyzes the incoming message from the Duwi device and updates
    the matching entities in Home Assistant accordingly.

    Args:
        hass: The instance of Home Assistant core.
        instance_id: A unique identifier associated with the Duwi device instance.
        message: The received message containing state information to be parsed and synchronized.

    Note:
        - The function ignores KEEPALIVE messages which don't carry state information.
        - It processes only certain namespaces that convey meaningful state changes.
    """
    _LOGGER.debug(f"Received message---------------: {message}")
    # Ignore KEEPALIVE messages as they do not contain state information.
    if message == "KEEPALIVE":
        _LOGGER.debug("Received KEEPALIVE message.")
        return

    # Attempting to parse the JSON message.
    try:
        message_data = json.loads(message)
    except json.JSONDecodeError:
        _LOGGER.error("Failed to parse message - Not a valid JSON string.")
        return

    namespace = message_data.get("namespace")

    # Proceed only with the expected namespaces.
    if namespace not in [
        "Duwi.RPS.DeviceValue",
        "Duwi.RPS.TerminalOnline",
        "Duwi.RPS.DeviceGroupValue",
    ]:
        _LOGGER.debug(f"Received message with unexpected namespace: {namespace}")
        return

    # Checking for a result within the message.
    result = message_data.get("result")
    if not result:
        _LOGGER.debug("Received message with no result.")
        return

    # Parsing the result if it's a string.
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            _LOGGER.error("Parsing error - result is not a valid JSON string.")
            return

    msg = result.get("msg")
    if not msg:
        _LOGGER.debug("Received message with no msg detail.")
        return

    # Handling TerminalOnline namespace separately.
    if namespace == "Duwi.RPS.TerminalOnline":
        sequence = msg.get("sequence")
        is_online = msg.get("online")
        _LOGGER.debug(f"Duwi.RPS.TerminalOnline {sequence} is online: {is_online}")

        device_updates = (
            hass.data[DOMAIN][instance_id].get("slave", {}).get(sequence, None)
        )
        if device_updates and (
            hass.data[DOMAIN][instance_id]
            .get("slave", {})
            .get(sequence, {})
            .get("is_follow_online")
            or not is_online
        ):
            # Sequence type is slave machine
            _LOGGER.debug(
                f"Slave update device online status: {hass.data[DOMAIN][instance_id].get('slave', {}).get(sequence, None)}"
            )
            for device_no, handler in device_updates.items():
                if callable(handler):
                    await handler(available=is_online)
            return

        terminals = hass.data[DOMAIN][instance_id].get("host", {}).get(sequence)
        if terminals and not is_online:
            # Sequence type is host engine
            _LOGGER.debug(
                f"host update device offline: {hass.data[DOMAIN][instance_id].get('slave', {}).get(sequence, None)}"
            )
            for terminal in terminals:
                device_updates = (
                    hass.data[DOMAIN][instance_id].get("slave", {}).get(terminal)
                )

                if device_updates is not None:
                    for device_no, handler in device_updates.items():
                        if callable(handler):
                            await handler(available=is_online)
        return

    # Extract device number and retrieve entity ID from Home Assistant data.
    device_no = msg.get("deviceNo", msg.get("deviceGroupNo"))
    if not device_no:
        _LOGGER.debug("Received message with no device_no")
        return

    if device_no not in hass.data[DOMAIN][instance_id]:
        _LOGGER.debug(f"Received message with unknown device_no: {device_no}")
        return

    # Prepare the action and attributes based on the message.
    action = "turn_on" if msg.get("switch") != "off" else "turn_off"

    attr_dict = {}

    _LOGGER.debug(f"Received message: {msg}")
    # Process light-specific attributes.
    if msg.get("online") is not None:
        action = None
        attr_dict["available"] = msg.get("online")

    if msg.get("light") is not None:
        attr_dict["brightness"] = int(round(msg.get("light") / 100 * 255))

    if msg.get("color_temp") is not None:
        color_temp_range = (
            hass.data[DOMAIN][instance_id].get(device_no, {}).get("color_temp_range")
        )
        ct = 500 - (int(round(msg.get("color_temp"))) - color_temp_range[0]) * (
            500 - 153
        ) / (color_temp_range[1] - color_temp_range[0])
        attr_dict["color_temp"] = int(ct)

    if msg.get("color") is not None:
        color_info = msg.get("color")
        hs_color = (color_info["h"], color_info["s"])
        brightness = int((color_info["v"] / 100) * 255)
        if brightness == 0:
            action = "turn_off"
        attr_dict["brightness"] = brightness
        attr_dict["hs_color"] = hs_color

    # Process cover-specific attributes.
    if msg.get("control_percent") is not None:
        action = "set_cover_position"
        attr_dict["position"] = msg.get("control_percent")

    if msg.get("light_angle") is not None or msg.get("angle_degree") is not None:
        action = "set_cover_tilt_position"
        angle = msg.get("light_angle", msg.get("angle_degree"))
        attr_dict["tilt_position"] = (180 - angle if angle > 90 else angle) / 90 * 100

    device = hass.data[DOMAIN][instance_id][device_no]

    _LOGGER.debug(
        f"Received message action: {action}, attributes: {attr_dict}, device: {device}"
    )
    await device.get("update_device_state")(
        action=action, is_scheduled=True, **attr_dict
    )


async def persist_messages_with_status_code(
    hass: HomeAssistant, status: Optional[str] = None, message: Optional[str] = None
) -> None:
    """Persists messages with specific status code.

    Args:
        hass (HomeAssistant): Instance of Home Assistant.
        status (str, optional): Status code. Defaults to None.
        message (str, optional): Message to be persisted. Defaults to None.
    """
    messages = {
        Code.SUCCESS.value: "Success",
        Code.SYS_ERROR.value: "System Error",
        Code.LOGIN_ERROR.value: "Login Error",
        Code.APP_KEY_ERROR.value: "App Key Error",
        Code.TIMESTAMP_TIMEOUT.value: "Timestamp Timeout",
        Code.SYSTEM_RATE_LIMIT.value: "System Rate Limit",
        Code.SYSTEM_MINUTE_RATE_LIMIT.value: "System Minute Rate Limit",
        Code.SYSTEM_HOUR_RATE_LIMIT.value: "System Hour Rate Limit",
        Code.GATEWAY_SYS_ERROR.value: "Gateway System Error",
    }

    if not message and status:
        message = messages.get(status, "Unknown error")

    _LOGGER.debug(f"Persist message: {message}")

    if message is None:
        return

    async_create_notification(
        hass=hass,
        message=message,
        title="Duwi Notification",
        notification_id="duwi_notification",
    )


def debounce(wait: int or float) -> Callable:
    """Decorator to debounce function calls.

    Args:
        wait (int or float): Seconds to wait before the next call to the function can be made.

    Returns:
        Callable: Decorator for the function.
    """

    def decorator(fn):
        async def debounced_fn(self, *args, **kwargs):
            if hasattr(self, "_debounce_timer") and self._debounce_timer:
                self._debounce_timer.cancel()

            async def delayed_execution():
                await asyncio.sleep(wait)
                await fn(self, *args, **kwargs)

            self._debounce_timer = asyncio.create_task(delayed_execution())

        return debounced_fn

    return decorator
