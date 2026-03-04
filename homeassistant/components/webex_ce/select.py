"""Select platform for Webex CE devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WebexCEConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming device
PARALLEL_UPDATES = 1

# Map display values to xAPI status values
STATE_MAP = {
    "awake": "Off",
    "halfwake": "Halfwake",
    "sleep": "Standby",
}

# Reverse map for status to option
STATUS_TO_OPTION = {v: k for k, v in STATE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebexCEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Webex CE select entities."""
    client = entry.runtime_data

    # Get device info for device registry
    device_info = await client.get_device_info()

    # Create device info dict
    device_info_dict = DeviceInfo(
        identifiers={(DOMAIN, device_info["serial"])},
        name=entry.title,
        manufacturer="Cisco",
        model=device_info["product"],
        sw_version=device_info["software_version"],
    )

    # Add standby select
    async_add_entities(
        [
            WebexCECameraPresetSelect(client, device_info_dict),
            WebexCEPresentationSourceSelect(client, device_info_dict),
            WebexCEStandbySelect(client, device_info_dict),
        ]
    )


class WebexCEStandbySelect(SelectEntity):
    """Representation of a Webex CE standby state select."""

    _attr_has_entity_name = True
    _attr_translation_key = "standby"
    _attr_options = ["awake", "halfwake", "sleep"]

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the select."""
        self._client = client
        self._attr_device_info = device_info
        # Extract serial from device info identifiers
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_standby"
        self._attr_current_option = None
        self._attr_icon = "mdi:monitor"

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()

        # Subscribe to standby status updates
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Standby"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        _LOGGER.debug("Received standby feedback for %s: %s", self.unique_id, params)

        # The params dict contains the status path and value
        # For Status/Standby, the value is directly at params['Status']['Standby']
        try:
            standby_data = params.get("Status", {}).get("Standby")
            # Standby can be a string directly or a dict with State key
            if isinstance(standby_data, dict):
                state = standby_data.get("State")
            else:
                state = standby_data
        except (AttributeError, KeyError, TypeError):
            _LOGGER.warning("Unexpected standby feedback format: %s", params)
            return

        # Convert xAPI state to option
        if state in STATUS_TO_OPTION:
            self._attr_current_option = STATUS_TO_OPTION[state]
            # Update icon based on state
            if state == "Standby":
                self._attr_icon = "mdi:power"
            elif state == "Halfwake":
                self._attr_icon = "mdi:power-sleep"
            else:  # Off (Awake)
                self._attr_icon = "mdi:monitor"
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Unknown standby state: %s", state)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_select_option(self, option: str) -> None:
        """Change the standby state."""
        _LOGGER.debug("Setting standby state to: %s", option)
        try:
            if option == "awake":
                # Awake - deactivate standby
                _LOGGER.debug("Executing: xCommand Standby Deactivate")
                await self._client.xcommand(["Standby", "Deactivate"])
                self._attr_icon = "mdi:monitor"
            elif option == "halfwake":
                # Halfwake
                _LOGGER.debug("Executing: xCommand Standby Halfwake")
                await self._client.xcommand(["Standby", "Halfwake"])
                self._attr_icon = "mdi:power-sleep"
            elif option == "sleep":
                # Full standby
                _LOGGER.debug("Executing: xCommand Standby Activate")
                await self._client.xcommand(["Standby", "Activate"])
                self._attr_icon = "mdi:power"
            else:
                _LOGGER.error("Invalid standby option: %s", option)
                return

            # Optimistically update the state
            self._attr_current_option = option
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Failed to set standby state to %s", option)
            raise


class WebexCEPresentationSourceSelect(SelectEntity):
    """Representation of presentation source select."""

    _attr_has_entity_name = True
    _attr_translation_key = "presentation_source"
    _attr_options = ["1", "2", "3", "4", "5"]

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the select."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_presentation_source"
        self._attr_current_option = None
        self._attr_icon = "mdi:video-input-hdmi"

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Configuration", "Video", "Input", "Connector"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            connector_data = (
                params.get("Configuration", {})
                .get("Video", {})
                .get("Input", {})
                .get("Connector")
            )
            if isinstance(connector_data, list):
                for connector in connector_data:
                    if (
                        isinstance(connector, dict)
                        and connector.get("PresentationSelection") == "Manual"
                    ):
                        source_id = connector.get("SourceId")
                        if source_id and str(source_id) in self._attr_options:
                            self._attr_current_option = str(source_id)
                            self.async_write_ha_state()
                            break
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.warning(
                "Unexpected presentation source feedback: %s - %s", params, err
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_select_option(self, option: str) -> None:
        """Change the presentation source."""
        try:
            await self._client.xconfiguration(
                [
                    "Video",
                    "Input",
                    "Connector",
                    option,
                    "PresentationSelection",
                ],
                Value="Manual",
            )
            # Also set the SourceId for this connector
            await self._client.xconfiguration(
                ["Video", "Input", "Connector", option, "SourceId"],
                Value=option,
            )
            self._attr_current_option = option
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Could not set presentation source to %s", option)
            raise


class WebexCECameraPresetSelect(SelectEntity):
    """Representation of camera preset select."""

    _attr_has_entity_name = True
    _attr_translation_key = "camera_preset"
    _attr_options = [str(i) for i in range(1, 36)]  # Presets 1-35

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the select."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_camera_preset"
        self._attr_current_option = None
        self._attr_icon = "mdi:camera-control"

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Cameras", "Camera"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            camera_data = params.get("Status", {}).get("Cameras", {}).get("Camera")
            if not isinstance(camera_data, list):
                return
            for camera in camera_data:
                if not isinstance(camera, dict):
                    continue
                position = camera.get("Position", {})
                if not isinstance(position, dict):
                    continue
                preset = position.get("ActivePreset")
                if preset and str(preset) in self._attr_options:
                    self._attr_current_option = str(preset)
                    self.async_write_ha_state()
                    break
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.warning("Unexpected camera preset feedback: %s - %s", params, err)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_select_option(self, option: str) -> None:
        """Activate the camera preset."""
        try:
            await self._client.xcommand(
                ["Camera", "Preset", "Activate"], PresetId=int(option)
            )
            self._attr_current_option = option
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Could not activate camera preset %s", option)
            raise
