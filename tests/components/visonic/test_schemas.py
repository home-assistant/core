"""Test Visonic form schemas and stored field representations."""

from probatio import Invalid, MultipleInvalid, to_field_list
import pytest

from homeassistant.components.visonic.config_flow import SERIAL_SCHEMA
from homeassistant.components.visonic.const import (
    CONF_CLOUD_APP_ID,
    CONF_DOWNLOAD_CODE,
    CONF_PANEL_NUMBER,
    CONF_PANEL_SERIAL,
    CONF_USER_CODE_SLOT,
    FORM_CLOUD,
    FORM_ETHERNET,
    FORM_POWERLINK,
    FORM_SELECT_PANEL,
)
from homeassistant.components.visonic.schemas import (
    CLOUD_PANEL_SCHEMA,
    CLOUD_SCHEMA,
    CONNECTION_SCHEMA,
    ETHERNET_SCHEMA,
    POWERLINK_SCHEMA,
)
from homeassistant.components.visonic.visonic_types import DeviceType
from homeassistant.const import (
    CONF_CODE,
    CONF_DEVICE,
    CONF_EMAIL,
    CONF_EXTERNAL_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)
from homeassistant.helpers import config_validation as cv

SCHEMAS = {
    FORM_CLOUD: CLOUD_SCHEMA,
    FORM_SELECT_PANEL: CLOUD_PANEL_SCHEMA,
    FORM_ETHERNET: ETHERNET_SCHEMA,
    FORM_POWERLINK: POWERLINK_SCHEMA,
}


def test_serial_device_required() -> None:
    """Serial setup requires a device path."""
    with pytest.raises(MultipleInvalid, match="required key not provided"):
        SERIAL_SCHEMA({})
    assert SERIAL_SCHEMA({CONF_DEVICE: "/dev/ttyUSB0"})[CONF_DEVICE] == "/dev/ttyUSB0"


def test_optional_download_code() -> None:
    """An omitted download code remains absent."""
    assert CONF_DOWNLOAD_CODE not in POWERLINK_SCHEMA({})


def test_cloud_polling_interval_not_configurable() -> None:
    """The panel form collects only its PIN and rejects polling settings."""
    assert CLOUD_PANEL_SCHEMA({}) == {CONF_CODE: "1111"}
    with pytest.raises(MultipleInvalid) as exc:
        CLOUD_PANEL_SCHEMA({CONF_SCAN_INTERVAL: 60})
    assert exc.value.path == [CONF_SCAN_INTERVAL]


@pytest.mark.parametrize(
    ("form", "field", "value", "expected"),
    [
        pytest.param(
            FORM_SELECT_PANEL, CONF_CODE, "0001", "0001", id="pin-leading-zero"
        ),
        pytest.param(
            FORM_POWERLINK,
            CONF_DOWNLOAD_CODE,
            "0001",
            "0001",
            id="download-leading-zero",
        ),
        pytest.param(FORM_POWERLINK, CONF_DOWNLOAD_CODE, "", "", id="download-empty"),
        pytest.param(
            FORM_POWERLINK, CONF_DOWNLOAD_CODE, "12ab", "12ab", id="download-lowercase"
        ),
        pytest.param(
            FORM_POWERLINK, CONF_DOWNLOAD_CODE, "AB12", "AB12", id="download-uppercase"
        ),
        pytest.param(
            FORM_POWERLINK, CONF_DOWNLOAD_CODE, "aB1f", "aB1f", id="download-mixed-case"
        ),
        pytest.param(FORM_ETHERNET, CONF_PORT, "1", "1", id="port-min"),
        pytest.param(FORM_ETHERNET, CONF_PORT, "65535", "65535", id="port-max"),
        pytest.param(FORM_ETHERNET, CONF_PORT, 1234, "1234", id="port-integer"),
    ],
)
def test_validated_fields(
    form: str, field: str, value: str | int, expected: str
) -> None:
    """Preserve credential strings and the stored port representation."""
    assert SCHEMAS[form]({field: value})[field] == expected


@pytest.mark.parametrize(
    ("form", "field", "value"),
    [
        pytest.param(FORM_SELECT_PANEL, CONF_CODE, "", id="pin-empty"),
        pytest.param(FORM_SELECT_PANEL, CONF_CODE, "123", id="pin-short"),
        pytest.param(FORM_SELECT_PANEL, CONF_CODE, "12345", id="pin-long"),
        pytest.param(FORM_SELECT_PANEL, CONF_CODE, "12ab", id="pin-letters"),
        pytest.param(FORM_SELECT_PANEL, CONF_CODE, "１２３４", id="pin-unicode"),
        pytest.param(FORM_SELECT_PANEL, CONF_CODE, "1234\n", id="pin-newline"),
        pytest.param(FORM_POWERLINK, CONF_DOWNLOAD_CODE, "123", id="download-short"),
        pytest.param(FORM_POWERLINK, CONF_DOWNLOAD_CODE, "12345", id="download-long"),
        pytest.param(FORM_POWERLINK, CONF_DOWNLOAD_CODE, "12ag", id="download-non-hex"),
        pytest.param(
            FORM_POWERLINK, CONF_DOWNLOAD_CODE, "１２３４", id="download-unicode"
        ),
        pytest.param(
            FORM_POWERLINK, CONF_DOWNLOAD_CODE, "1234\n", id="download-newline"
        ),
        pytest.param(FORM_ETHERNET, CONF_PORT, "0", id="port-zero"),
        pytest.param(FORM_ETHERNET, CONF_PORT, "65536", id="port-too-large"),
        pytest.param(FORM_ETHERNET, CONF_PORT, "-1", id="port-negative"),
        pytest.param(FORM_ETHERNET, CONF_PORT, "1.5", id="port-fraction"),
        pytest.param(FORM_ETHERNET, CONF_PORT, "abc", id="port-letters"),
    ],
)
def test_invalid_fields(form: str, field: str, value: str) -> None:
    """Reject invalid input at its field before advancing the flow."""
    with pytest.raises(MultipleInvalid) as exc:
        SCHEMAS[form]({field: value})
    assert exc.value.path == [field]


@pytest.mark.parametrize(
    ("form", "field"),
    [
        pytest.param(FORM_SELECT_PANEL, CONF_CODE, id="pin"),
        pytest.param(FORM_POWERLINK, CONF_DOWNLOAD_CODE, id="download"),
        pytest.param(FORM_ETHERNET, CONF_PORT, id="port"),
    ],
)
def test_validated_fields_serialize(form: str, field: str) -> None:
    """The frontend can render forms containing the new validators."""
    fields = to_field_list(SCHEMAS[form], custom_serializer=cv.custom_serializer)
    serialized = next(item for item in fields if item["name"] == field)
    assert serialized["type"] == "string"
    assert serialized["secret"] is True


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            {
                CONF_TYPE: DeviceType.ETHERNET,
                CONF_PANEL_NUMBER: 2,
                CONF_HOST: "192.0.2.1",
                CONF_PORT: "1234",
            },
            id="ethernet-basic",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.ETHERNET,
                CONF_PANEL_NUMBER: 2,
                CONF_HOST: "192.0.2.1",
                CONF_PORT: "1234",
                CONF_DOWNLOAD_CODE: "0001",
                CONF_USER_CODE_SLOT: 2,
            },
            id="ethernet-powerlink",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.SERIAL,
                CONF_PANEL_NUMBER: 2,
                CONF_DEVICE: "/dev/ttyUSB0",
            },
            id="serial-basic",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.SERIAL,
                CONF_PANEL_NUMBER: 2,
                CONF_DEVICE: "/dev/ttyUSB0",
                CONF_DOWNLOAD_CODE: "0001",
                CONF_USER_CODE_SLOT: 2,
            },
            id="serial-powerlink",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.CLOUD,
                CONF_PANEL_NUMBER: 2,
                CONF_EXTERNAL_URL: "cloud.example.com",
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "password",
                CONF_CODE: "0001",
                CONF_PANEL_SERIAL: "ABCDEF",
                CONF_CLOUD_APP_ID: "existing-app-id",
            },
            id="cloud",
        ),
    ],
)
def test_connection_schema(data: dict[str, str | int]) -> None:
    """Select the complete connection schema from its stored type."""
    result = CONNECTION_SCHEMA(data)
    assert result.items() >= data.items()
    assert result[CONF_TYPE] == data[CONF_TYPE]
    assert result[CONF_PANEL_NUMBER] == 2


@pytest.mark.parametrize(
    ("data", "field"),
    [
        pytest.param({CONF_PANEL_NUMBER: 2}, CONF_TYPE, id="missing-type"),
        pytest.param(
            {
                CONF_TYPE: DeviceType.SERIAL,
                CONF_DEVICE: "/dev/ttyUSB0",
            },
            CONF_PANEL_NUMBER,
            id="missing-panel-number",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.SERIAL,
                CONF_DEVICE: "/dev/ttyUSB0",
                CONF_PANEL_NUMBER: None,
            },
            CONF_PANEL_NUMBER,
            id="null-panel-number",
        ),
        pytest.param(
            {CONF_TYPE: "unknown", CONF_PANEL_NUMBER: 2}, CONF_TYPE, id="unknown-type"
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.ETHERNET,
                CONF_PANEL_NUMBER: 2,
                CONF_DEVICE: "/dev/ttyUSB0",
                CONF_PORT: "1234",
            },
            CONF_HOST,
            id="ethernet-missing-host",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.ETHERNET,
                CONF_PANEL_NUMBER: 2,
                CONF_HOST: "192.0.2.1",
            },
            CONF_PORT,
            id="ethernet-missing-port",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.ETHERNET,
                CONF_PANEL_NUMBER: 2,
                CONF_HOST: "192.0.2.1",
                CONF_PORT: "65536",
            },
            CONF_PORT,
            id="ethernet-invalid-port",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.SERIAL,
                CONF_PANEL_NUMBER: 2,
                CONF_HOST: "192.0.2.1",
                CONF_PORT: "1234",
            },
            CONF_DEVICE,
            id="serial-missing-device",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.SERIAL,
                CONF_PANEL_NUMBER: 2,
                CONF_DEVICE: "/dev/ttyUSB0",
                CONF_DOWNLOAD_CODE: "12ag",
            },
            CONF_DOWNLOAD_CODE,
            id="serial-invalid-download-code",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.CLOUD,
                CONF_PANEL_NUMBER: 2,
                CONF_EXTERNAL_URL: "cloud.example.com",
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "password",
                CONF_CODE: "12ab",
                CONF_PANEL_SERIAL: "ABCDEF",
                CONF_CLOUD_APP_ID: "app-id",
            },
            CONF_CODE,
            id="cloud-invalid-pin",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.CLOUD,
                CONF_PANEL_NUMBER: 2,
                CONF_EXTERNAL_URL: "cloud.example.com",
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "password",
                CONF_CODE: "0001",
                CONF_PANEL_SERIAL: "ABCDEF",
            },
            CONF_CLOUD_APP_ID,
            id="cloud-missing-app-id",
        ),
    ],
)
def test_connection_schema_invalid_branch(
    data: dict[str, str | int], field: str
) -> None:
    """Report errors from the selected branch without falling back to another type."""
    with pytest.raises(Invalid) as exc:
        CONNECTION_SCHEMA(data)
    assert exc.value.path == [field]


def test_connection_schema_normalizes_port() -> None:
    """Complete-data validation retains the stored string representation of a port."""
    result = CONNECTION_SCHEMA(
        {
            CONF_TYPE: DeviceType.ETHERNET,
            CONF_PANEL_NUMBER: 2,
            CONF_HOST: "192.0.2.1",
            CONF_PORT: 1234,
        }
    )
    assert result[CONF_PORT] == "1234"
    assert CONF_USER_CODE_SLOT not in result
    assert CONF_DOWNLOAD_CODE not in result
