"""Utility functions for the MQTT integration."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_PAYLOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
    CONF_CERTIFICATE,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    DATA_MQTT,
    DEFAULT_ENCODING,
    DEFAULT_QOS,
    DEFAULT_RETAIN,
    DOMAIN,
)
from .models import MqttData

TEMP_DIR_NAME = f"home-assistant-{DOMAIN}"


def mqtt_config_entry_enabled(hass: HomeAssistant) -> bool | None:
    """Return true when the MQTT config entry is enabled."""
    if not bool(hass.config_entries.async_entries(DOMAIN)):
        return None
    return not bool(hass.config_entries.async_entries(DOMAIN)[0].disabled_by)


def valid_topic(topic: Any) -> str:
    """Validate that this is a valid topic name/filter."""
    validated_topic = cv.string(topic)
    try:
        raw_validated_topic = validated_topic.encode("utf-8")
    except UnicodeError as err:
        raise vol.Invalid("MQTT topic name/filter must be valid UTF-8 string.") from err
    if not raw_validated_topic:
        raise vol.Invalid("MQTT topic name/filter must not be empty.")
    if len(raw_validated_topic) > 65535:
        raise vol.Invalid(
            "MQTT topic name/filter must not be longer than 65535 encoded bytes."
        )
    if "\0" in validated_topic:
        raise vol.Invalid("MQTT topic name/filter must not contain null character.")
    if any(char <= "\u001F" for char in validated_topic):
        raise vol.Invalid("MQTT topic name/filter must not contain control characters.")
    if any("\u007f" <= char <= "\u009F" for char in validated_topic):
        raise vol.Invalid("MQTT topic name/filter must not contain control characters.")
    if any("\ufdd0" <= char <= "\ufdef" for char in validated_topic):
        raise vol.Invalid("MQTT topic name/filter must not contain non-characters.")
    if any((ord(char) & 0xFFFF) in (0xFFFE, 0xFFFF) for char in validated_topic):
        raise vol.Invalid("MQTT topic name/filter must not contain noncharacters.")

    return validated_topic


def valid_subscribe_topic(topic: Any) -> str:
    """Validate that we can subscribe using this MQTT topic."""
    validated_topic = valid_topic(topic)
    for i in (i for i, c in enumerate(validated_topic) if c == "+"):
        if (i > 0 and validated_topic[i - 1] != "/") or (
            i < len(validated_topic) - 1 and validated_topic[i + 1] != "/"
        ):
            raise vol.Invalid(
                "Single-level wildcard must occupy an entire level of the filter"
            )

    index = validated_topic.find("#")
    if index != -1:
        if index != len(validated_topic) - 1:
            # If there are multiple wildcards, this will also trigger
            raise vol.Invalid(
                "Multi-level wildcard must be the last "
                "character in the topic filter."
            )
        if len(validated_topic) > 1 and validated_topic[index - 1] != "/":
            raise vol.Invalid(
                "Multi-level wildcard must be after a topic level separator."
            )

    return validated_topic


def valid_subscribe_topic_template(value: Any) -> template.Template:
    """Validate either a jinja2 template or a valid MQTT subscription topic."""
    tpl = template.Template(value)

    if tpl.is_static:
        valid_subscribe_topic(value)

    return tpl


def valid_publish_topic(topic: Any) -> str:
    """Validate that we can publish using this MQTT topic."""
    validated_topic = valid_topic(topic)
    if "+" in validated_topic or "#" in validated_topic:
        raise vol.Invalid("Wildcards can not be used in topic names")
    return validated_topic


_VALID_QOS_SCHEMA = vol.All(vol.Coerce(int), vol.In([0, 1, 2]))

MQTT_WILL_BIRTH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TOPIC): valid_publish_topic,
        vol.Required(ATTR_PAYLOAD, CONF_PAYLOAD): cv.string,
        vol.Optional(ATTR_QOS, default=DEFAULT_QOS): _VALID_QOS_SCHEMA,
        vol.Optional(ATTR_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    },
    required=True,
)


def get_mqtt_data(hass: HomeAssistant, ensure_exists: bool = False) -> MqttData:
    """Return typed MqttData from hass.data[DATA_MQTT]."""
    if ensure_exists:
        return hass.data.setdefault(DATA_MQTT, MqttData())
    return hass.data[DATA_MQTT]


async def async_create_certificate_temp_files(
    hass: HomeAssistant, config: ConfigType
) -> None:
    """Create certificate temporary files for the MQTT client."""

    def _create_temp_file(temp_file: Path, data: str | None) -> None:
        if data is None or data == "auto":
            if temp_file.exists():
                os.remove(Path(temp_file))
            return
        temp_file.write_text(data)

    def _create_temp_dir_and_files() -> None:
        """Create temporary directory."""
        temp_dir = Path(tempfile.gettempdir()) / TEMP_DIR_NAME

        if (
            config.get(CONF_CERTIFICATE)
            or config.get(CONF_CLIENT_CERT)
            or config.get(CONF_CLIENT_KEY)
        ) and not temp_dir.exists():
            temp_dir.mkdir(0o700)

        _create_temp_file(temp_dir / CONF_CERTIFICATE, config.get(CONF_CERTIFICATE))
        _create_temp_file(temp_dir / CONF_CLIENT_CERT, config.get(CONF_CLIENT_CERT))
        _create_temp_file(temp_dir / CONF_CLIENT_KEY, config.get(CONF_CLIENT_KEY))

    await hass.async_add_executor_job(_create_temp_dir_and_files)


def get_file_path(option: str, default: str | None = None) -> Path | str | None:
    """Get file path of a certificate file."""
    temp_dir = Path(tempfile.gettempdir()) / TEMP_DIR_NAME
    if not temp_dir.exists():
        return default

    file_path: Path = temp_dir / option
    if not file_path.exists():
        return default

    return temp_dir / option


def migrate_certificate_file_to_content(file_name_or_auto: str) -> str | None:
    """Convert certificate file or setting to config entry setting."""
    if file_name_or_auto == "auto":
        return "auto"
    try:
        with open(file_name_or_auto, encoding=DEFAULT_ENCODING) as certiticate_file:
            return certiticate_file.read()
    except OSError:
        return None
