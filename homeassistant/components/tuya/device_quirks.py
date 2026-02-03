"""Device quirks for Tuya devices."""

import base64
from typing import Any

from tuya_sharing import CustomerDevice

from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN

# Internal representation of a feeding time entry to keep it easier to tell what we expect.
FeedingTime = dict[str, int]
TEMPLATE_FULL = [
    ("days", 2),
    ("hour", 2),
    ("minute", 2),
    ("portion", 2),
    ("enabled", 2),
]
DAY_MAPPING = [(i, i) for i in range(7)]

DEFAULT_PROFILE_DEVICES = {
    "wfkzyy0evslzsmoi",
}

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def days_bitmap_to_names(entry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert bitmap integer to list of day names."""
    for item in entry:
        bitmask = item.get("days", 0)
        item["days"] = [DAYS[i] for i in range(7) if bitmask & (1 << i)]
    return entry


def days_names_to_bitmap(entry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert list of day names to bitmap integer."""
    for item in entry:
        bitmask = 0
        for day in item.get("days", []):
            if day in DAYS:
                bitmask |= 1 << DAYS.index(day)
        item["days"] = bitmask
    return entry


def create_day_transformer(mapping: list[tuple]):
    """mapping: list of (internal_bit, device_bit)."""

    def encode_entry(entry: FeedingTime) -> FeedingTime:
        if "days" not in entry:
            return entry
        val = 0
        for internal, device in mapping:
            if entry["days"] & (1 << internal):
                val |= 1 << device
        entry["days"] = val & 0x7F
        return entry

    def decode_entry(entry: FeedingTime) -> FeedingTime:
        if "days" not in entry:
            return entry
        val = 0
        masked = entry["days"] & 0x7F
        for internal, device in mapping:
            if masked & (1 << device):
                val |= 1 << internal
        entry["days"] = val
        return entry

    return {"encode": encode_entry, "decode": decode_entry}


class TemplateEncoder:
    """Encoder/decoder for templated meal plan data."""

    def __init__(self, template: list[tuple], profile: dict[str, Any]) -> None:
        """Initialize TemplateEncoder."""
        self.tokens = template
        self.profile = profile

    def encode(self, data: list[FeedingTime]) -> str:
        """Encode meal plan data to hex string."""
        return "".join(self.serialize_entry(entry) for entry in data)

    def decode(self, data: str) -> list[FeedingTime]:
        """Decode hex string to meal plan data."""
        chunk_len = sum(width for _, width in self.tokens)
        if len(data) % chunk_len != 0:
            raise ValueError("Invalid templated meal plan length")
        return [
            self.parse_entry(data[i : i + chunk_len])
            for i in range(0, len(data), chunk_len)
        ]

    def serialize_entry(self, data: FeedingTime) -> str:
        """Serialize a single meal plan entry to hex string."""
        if self.profile and "encode" in self.profile:
            entry = self.profile["encode"](data)
        return "".join(
            f"{entry.get(field, 0):0{width}x}" for field, width in self.tokens
        )

    def parse_entry(self, chunk: str) -> FeedingTime:
        """Parse a single meal plan entry from hex string."""
        entry: FeedingTime = {}
        pos = 0
        for field, width in self.tokens:
            segment = chunk[pos : pos + width]
            pos += width
            if segment:
                entry[field] = int(segment, 16)
        if self.profile and "decode" in self.profile:
            entry = self.profile["decode"](entry)
        return entry


class Base64Encoder:
    """Encoder/decoder for Base64 meal plan data."""

    def __init__(self, profile: dict[str, Any]) -> None:
        """Initialize Base64Encoder."""
        template = profile.get("template")
        if not template:
            raise ValueError("Profile must define template")
        self.encoder = TemplateEncoder(template, profile)

    def encode(self, data: list[dict[str, Any]]) -> str:
        """Encode meal plan data to Base64 string."""
        hex_str = self.encoder.encode(data)
        v = bytes(int(hex_str[i : i + 2], 16) for i in range(0, len(hex_str), 2))
        return base64.b64encode(v).decode()

    def decode(self, b64_data: str) -> list[dict[str, Any]]:
        """Decode Base64 string to meal plan data."""
        if not b64_data or b64_data.lower() == "unknown":
            raise ValueError("Invalid Base64 meal plan data")
        hex_str = "".join(f"{byte:02x}" for byte in base64.b64decode(b64_data))
        return self.encoder.decode(hex_str)


def get_meal_plan_serializer(device: CustomerDevice):
    """Get the profile string for a given device."""

    if device.product_id in DEFAULT_PROFILE_DEVICES:
        return Base64Encoder(
            {
                "template": TEMPLATE_FULL,
                "encode": create_day_transformer(DAY_MAPPING)["encode"],
                "decode": create_day_transformer(DAY_MAPPING)["decode"],
            }
        )
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="device_missing_serializer",
        translation_placeholders={"device_id": device.id},
    )


def json_to_meal_data_1(data: str):
    """Decode meal_plan data from JSON format."""
    raise NotImplementedError("JSON meal plan decoding not implemented yet.")
