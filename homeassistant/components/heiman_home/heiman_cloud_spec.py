"""Heiman Cloud Spec Parser.

Parses device specifications from Heiman cloud API or local JSON files.
Provides device type to Home Assistant entity mapping rules.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _read_spec_file(json_file: Path) -> dict[str, Any]:
    """Read a spec JSON file from disk."""
    with open(json_file, encoding="utf-8") as file_handle:
        return json.load(file_handle)


class HeimanCloudSpecParser:
    """Heiman Cloud Specification Parser."""

    # Device type to HA platform mapping
    DEVICE_TYPE_MAP = {
        # Sensors
        "temperature-sensor": {"platform": "sensor", "device_class": "temperature"},
        "humidity-sensor": {"platform": "sensor", "device_class": "humidity"},
        "temperature-humidity-sensor": {"platform": "sensor"},
        "smoke-detector": {"platform": "binary_sensor", "device_class": "smoke"},
        "gas-detector": {"platform": "binary_sensor", "device_class": "gas"},
        "co-detector": {"platform": "binary_sensor", "device_class": "gas"},
        "motion-sensor": {"platform": "binary_sensor", "device_class": "motion"},
        "door-window-sensor": {"platform": "binary_sensor", "device_class": "door"},
        "water-leak-sensor": {"platform": "binary_sensor", "device_class": "moisture"},
        "heat-detector": {"platform": "binary_sensor", "device_class": "heat"},
        # Control devices
        "switch": {"platform": "switch"},
        "light": {"platform": "light"},
        "fan": {"platform": "fan"},
        "cover": {"platform": "cover"},
        "humidifier": {"platform": "humidifier"},
        "vacuum": {"platform": "vacuum"},
        "water-heater": {"platform": "water_heater"},
        # Media
        "media-player": {"platform": "media_player"},
        # Gateway
        "gateway": {"platform": "sensor"},
    }

    def __init__(
        self,
        hass: HomeAssistant,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        """Initialize the spec parser."""
        self.hass = hass
        self.loop = loop or asyncio.get_event_loop()
        self._spec_cache: dict[str, dict] = {}
        self._device_type_cache: dict[str, str] = {}
        self._json_dir: Path | None = None

        # Try to find heiman_doc/json directory
        possible_paths = [
            Path(hass.config.path("heiman_doc", "json")),
            Path(hass.config.path(".storage", "heiman_home", "json")),
            Path(__file__).parent.parent.parent / "heiman_doc" / "json",
        ]

        for path in possible_paths:
            if path.exists():
                self._json_dir = path
                _LOGGER.info("Found heiman JSON directory: %s", self._json_dir)
                break

    async def init_async(self) -> None:
        """Initialize the parser (load cached specs)."""
        if self._json_dir and self._json_dir.exists():
            await self._load_local_specs()

    async def deinit_async(self) -> None:
        """Deinitialize the parser."""
        self._spec_cache.clear()
        self._device_type_cache.clear()

    async def _load_local_specs(self) -> None:
        """Load specifications from local JSON files."""
        if not self._json_dir:
            return

        try:
            json_files = list(self._json_dir.glob("*.json"))
            _LOGGER.info("Found %d local specification files", len(json_files))

            for json_file in json_files:
                try:
                    spec_data = await asyncio.to_thread(_read_spec_file, json_file)

                    # Extract product ID or model from filename
                    model = (
                        json_file.stem.split("-")[0]
                        if "-" in json_file.stem
                        else json_file.stem
                    )

                    if "product_id" in spec_data:
                        product_id = spec_data["product_id"]
                        self._spec_cache[product_id] = spec_data
                        _LOGGER.debug("Loaded spec for product: %s", product_id)

                    if "model" in spec_data:
                        model = spec_data["model"]
                        self._spec_cache[model] = spec_data

                except (OSError, json.JSONDecodeError, TypeError, ValueError) as err:
                    _LOGGER.warning("Failed to load spec from %s: %s", json_file, err)

        except OSError as err:
            _LOGGER.error("Failed to load local specs: %s", err)

    async def parse_device_spec(
        self,
        device_info: dict,
        cloud_client: Any | None = None,
    ) -> dict | None:
        """Parse device specification.

        Args:
            device_info: Device information from API
            cloud_client: Cloud client instance for fetching specs

        Returns:
            Parsed specification data or None
        """
        product_id = device_info.get("productId", "")
        model = device_info.get("model", "")
        device_info.get("deviceType", "")

        # Check cache first
        cache_key = product_id or model
        if cache_key in self._spec_cache:
            _LOGGER.debug("Using cached spec for: %s", cache_key)
            return self._spec_cache[cache_key]

        # Try to load from local files
        if self._json_dir:
            await self._load_local_specs()
            if cache_key in self._spec_cache:
                return self._spec_cache[cache_key]

        # Try to fetch from cloud if cloud_client is available
        if cloud_client:
            try:
                spec_data = await cloud_client.async_get_device_spec(product_id)
                if spec_data:
                    self._spec_cache[cache_key] = spec_data
                    _LOGGER.info("Fetched spec from cloud for: %s", cache_key)
                    return spec_data
            except (AttributeError, KeyError, OSError, TypeError, ValueError) as err:
                _LOGGER.debug("Failed to fetch spec from cloud: %s", err)

        # Generate basic spec from device info
        _LOGGER.info(
            "Generating basic spec for device: %s",
            device_info.get("deviceName", "Unknown"),
        )
        return self._generate_basic_spec(device_info)

    def _generate_basic_spec(self, device_info: dict) -> dict:
        """Generate basic specification from device information."""
        device_info.get("deviceType", "unknown")
        product_name = device_info.get("productName", "")
        model = device_info.get("model", "")

        # Detect device type from product name
        detected_type = self._detect_device_type(product_name)

        spec = {
            "product_id": device_info.get("productId", ""),
            "model": model,
            "device_type": detected_type,
            "properties": [],
            "services": [],
            "actions": [],
            "events": [],
        }

        # Add common properties based on detected type
        base_props = self._get_base_properties(detected_type)
        spec["properties"].extend(base_props)

        return spec

    def _detect_device_type(self, product_name: str) -> str:
        """Detect device type from product name."""
        name_lower = product_name.lower()

        # Temperature/Humidity sensors
        if any(kw in name_lower for kw in ["temp", "湿度", "温感", "th", "ht"]):
            if "湿" in name_lower or "hum" in name_lower:
                return "temperature-humidity-sensor"
            if "温" in name_lower or "temp" in name_lower:
                return "temperature-sensor"
            return "humidity-sensor"

        # Safety detectors
        if "烟" in name_lower or "smoke" in name_lower:
            return "smoke-detector"
        if "气" in name_lower or "gas" in name_lower or "co" in name_lower:
            return "gas-detector"
        if "红" in name_lower or "motion" in name_lower or "pir" in name_lower:
            return "motion-sensor"
        if "门" in name_lower or "门磁" in name_lower or "door" in name_lower:
            return "door-window-sensor"
        if "水" in name_lower or "water" in name_lower or "leak" in name_lower:
            return "water-leak-sensor"
        if "热" in name_lower or "heat" in name_lower:
            return "heat-detector"

        # Control devices
        if "灯" in name_lower or "light" in name_lower:
            return "light"
        if "风" in name_lower or "fan" in name_lower:
            return "fan"
        if "帘" in name_lower or "cover" in name_lower:
            return "cover"
        if "湿" in name_lower and "器" in name_lower:
            return "humidifier"
        if "尘" in name_lower or "vacuum" in name_lower:
            return "vacuum"
        if "热水" in name_lower or ("water" in name_lower and "heater" in name_lower):
            return "water-heater"

        # Default to sensor
        return "sensor"

    def _get_base_properties(self, device_type: str) -> list[dict]:
        """Get base properties for a device type."""
        props = []

        if device_type in ["temperature-sensor", "temperature-humidity-sensor"]:
            props.append(
                {
                    "id": "CurrentTemperature",
                    "name": "Temperature",
                    "type": "sensor",
                    "data_type": "float",
                    "unit": "°C",
                    "device_class": "temperature",
                },
            )

        if device_type in ["humidity-sensor", "temperature-humidity-sensor"]:
            props.append(
                {
                    "id": "CurrentHumidity",
                    "name": "Humidity",
                    "type": "sensor",
                    "data_type": "float",
                    "unit": "%",
                    "device_class": "humidity",
                },
            )

        if device_type in [
            "smoke-detector",
            "gas-detector",
            "motion-sensor",
            "door-window-sensor",
            "water-leak-sensor",
            "heat-detector",
        ]:
            props.append(
                {
                    "id": "SensorState",
                    "name": "Status",
                    "type": "binary_sensor",
                    "data_type": "bool",
                    "device_class": self.DEVICE_TYPE_MAP.get(device_type, {}).get(
                        "device_class",
                        "safety",
                    ),
                },
            )

        # Common properties for all devices
        props.append(
            {
                "id": "BatteryPercentage",
                "name": "Battery",
                "type": "sensor",
                "data_type": "int",
                "unit": "%",
                "device_class": "battery",
            },
        )

        props.append(
            {
                "id": "RSSI",
                "name": "Signal Strength",
                "type": "sensor",
                "data_type": "int",
                "unit": "dBm",
                "device_class": "signal_strength",
            },
        )

        return props

    def get_entity_mapping(self, device_type: str) -> dict:
        """Get entity mapping for a device type.

        Args:
            device_type: Device type string

        Returns:
            Mapping dictionary with platform and device_class
        """
        return self.DEVICE_TYPE_MAP.get(
            device_type,
            {"platform": "sensor", "device_class": None},
        )

    def map_device_to_platform(self, device_info: dict) -> str:
        """Map device to appropriate HA platform.

        Args:
            device_info: Device information

        Returns:
            Platform string (sensor, binary_sensor, switch, etc.)
        """
        device_type = device_info.get("deviceType", "")
        mapping = self.get_entity_mapping(device_type)
        return mapping.get("platform", "sensor")

    async def get_all_supported_models(self) -> set[str]:
        """Get all supported device models.

        Returns:
            Set of model strings
        """
        models = set()

        # From cache
        for spec in self._spec_cache.values():
            if "model" in spec:
                models.add(spec["model"])

        # From JSON files
        if self._json_dir:
            for json_file in self._json_dir.glob("*.json"):
                try:
                    spec_data = await asyncio.to_thread(_read_spec_file, json_file)
                    if "model" in spec_data:
                        models.add(spec_data["model"])
                except OSError, json.JSONDecodeError, KeyError, TypeError, ValueError:
                    continue

        return models


class HeimanDeviceSpec:
    """Represents a parsed device specification."""

    def __init__(self, spec_data: dict):
        """Initialize device spec."""
        self.product_id = spec_data.get("product_id", "")
        self.model = spec_data.get("model", "")
        self.device_type = spec_data.get("device_type", "unknown")
        self.properties = spec_data.get("properties", [])
        self.services = spec_data.get("services", [])
        self.actions = spec_data.get("actions", [])
        self.events = spec_data.get("events", [])

    def get_property_by_id(self, property_id: str) -> dict | None:
        """Get property by ID."""
        for prop in self.properties:
            if prop.get("id") == property_id:
                return prop
        return None

    def get_properties_by_type(self, prop_type: str) -> list[dict]:
        """Get properties by type."""
        return [p for p in self.properties if p.get("type") == prop_type]
