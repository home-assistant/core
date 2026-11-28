"""Test the APsystems Lake_6 API client."""

import pytest
from pytest_homeassistant.plugins import AiohttpClientMocker

from homeassistant.components.apsystems.lake6.client import (
    Lake6ApiClient,
    Lake6ApiError,
    Lake6TouRule,
    parse_alarms,
    parse_control_panel,
    parse_device,
    parse_energies,
    parse_modes,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import (
    LAKE6_ACTIVE_PAYLOAD,
    LAKE6_ALARMS_PAYLOAD,
    LAKE6_DEV_ID,
    LAKE6_DEVICES_PAYLOAD,
    LAKE6_ENERGIES_PAYLOAD,
    LAKE6_IDLE_PAYLOAD,
    LAKE6_IP,
    LAKE6_MODES_PAYLOAD,
)

DEVICES_URL = f"http://{LAKE6_IP}/devices"
MODES_URL = f"http://{LAKE6_IP}/modes"
CONTROL_PANELS_URL = f"http://{LAKE6_IP}/control-panels"


def test_parse_device() -> None:
    """Test the /devices payload is decoded."""
    device = parse_device(LAKE6_DEVICES_PAYLOAD)

    assert device.dev_id == LAKE6_DEV_ID
    assert device.device_type == "Ema"
    assert device.sw_version == "V1.5.2"
    assert device.battery_capacity == 5.0
    assert device.rssi == -52


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="missing"),
        pytest.param({"dev_id": ""}, id="blank"),
        pytest.param({"dev_id": 1}, id="not-a-string"),
    ],
)
def test_parse_device_requires_dev_id(payload: dict[str, object]) -> None:
    """Test a payload without a usable device id is rejected."""
    with pytest.raises(ValueError, match="no usable dev_id"):
        parse_device(payload)


def test_parse_device_blank_firmware() -> None:
    """Test an empty firmware version becomes None so the row is hidden."""
    device = parse_device({"dev_id": LAKE6_DEV_ID, "dev_ver": "  "})

    assert device.sw_version is None
    assert device.device_type == ""


def test_parse_energies() -> None:
    """Test the /energies payload is decoded, ints and floats apart."""
    energies = parse_energies(LAKE6_ENERGIES_PAYLOAD)

    assert energies.battery_soc == 30.0
    assert energies.battery_temperature == 25.0
    assert energies.device_temperature == 31.0
    assert energies.battery_charge_energy == 57.288
    assert energies.battery_discharge_energy == 12.5
    assert energies.grid_export_energy == 100.1
    assert energies.grid_import_energy == 200.2
    assert energies.offgrid_export_energy == 0.0
    assert energies.offgrid_import_energy == 0.0
    # Power fields are plain integers on the wire.
    assert energies.battery_power == -486
    assert energies.grid_power == 1200
    assert energies.offgrid_power == 0
    assert energies.battery_status == "charging"


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("not-a-number", id="text"),
        pytest.param("NaN", id="nan"),
        pytest.param("inf", id="infinity"),
        pytest.param(None, id="null"),
        pytest.param(True, id="bool"),
    ],
)
def test_parse_energies_drops_unusable_numbers(value: object) -> None:
    """Test one bad field becomes None without affecting the response."""
    energies = parse_energies({"bat_soc": value, "bat_power": value})

    assert energies.battery_soc is None
    assert energies.battery_power is None


def test_parse_energies_accepts_json_numbers() -> None:
    """Test numbers and numeric strings are both accepted."""
    energies = parse_energies({"bat_soc": 30, "bat_power": "486.7"})

    assert energies.battery_soc == 30.0
    # Fractional power is truncated, matching how the device rounds.
    assert energies.battery_power == 486


def test_parse_alarms() -> None:
    """Test the /alarms payload is decoded to booleans."""
    alarms = parse_alarms(LAKE6_ALARMS_PAYLOAD)

    assert alarms.battery_over_temperature is True
    assert alarms.battery_under_temperature is False
    assert alarms.device_temperature_protection is False


def test_parse_alarms_accepts_ints() -> None:
    """Test the device quoting is not relied upon."""
    alarms = parse_alarms({"bat_overtemp": 1, "bat_undertemp": 0, "bat_ie": 2})

    assert alarms.battery_over_temperature is True
    assert alarms.battery_under_temperature is False
    assert alarms.battery_internal_error is None


def test_parse_modes() -> None:
    """Test the /modes payload is decoded, including the schedule."""
    modes = parse_modes(LAKE6_MODES_PAYLOAD)

    assert modes.operating_mode == "time_of_use"
    assert modes.eco is False
    assert modes.depth_of_discharge == 15
    assert len(modes.time_cfg) == 2
    assert modes.tou_rules == [
        Lake6TouRule(
            enabled=True,
            weekdays=[1, 2, 3, 4, 5],
            start="09:00",
            end="09:10",
            function="discharge",
            power=200,
        ),
        Lake6TouRule(
            enabled=True,
            weekdays=[6, 7],
            start="10:00",
            end="10:10",
            function="self_consumption",
            power=None,
        ),
    ]


def test_parse_modes_unknown_codes() -> None:
    """Test unknown enumerations do not break the entity layer."""
    modes = parse_modes({"mode": "9", "eco": "yes", "dod": "abc", "time_cfg": "x"})

    assert modes.operating_mode is None
    assert modes.eco is None
    assert modes.depth_of_discharge is None
    assert modes.time_cfg == []
    assert modes.tou_rules == []


def test_parse_control_panel_idle() -> None:
    """Test an idle panel reports no window and no timestamp width."""
    panel = parse_control_panel(LAKE6_IDLE_PAYLOAD)

    assert panel.active is False
    assert panel.windows == []
    assert panel.timestamp_width is None


def test_parse_control_panel_active() -> None:
    """Test a running window is decoded, 28 digits echoed back as 28."""
    panel = parse_control_panel(LAKE6_ACTIVE_PAYLOAD)

    assert panel.active is True
    assert panel.timestamp_width == 14
    assert len(panel.windows) == 1
    window = panel.windows[0]
    assert window.start.isoformat() == "2026-11-25T10:00:00"
    assert window.end.isoformat() == "2026-11-25T10:30:00"
    assert window.power == 500


def test_parse_control_panel_minute_form() -> None:
    """Test the 24 digit form from the manual is accepted."""
    panel = parse_control_panel(
        {"mode": "1", "MI1": {"time": ["202611251000202611251030"], "power": ["0"]}}
    )

    assert panel.timestamp_width == 12
    assert panel.windows[0].start.isoformat() == "2026-11-25T10:00:00"
    assert panel.windows[0].end.isoformat() == "2026-11-25T10:30:00"


def test_parse_control_panel_drops_malformed_pairs() -> None:
    """Test a power without its slot does not shift the following pairs."""
    panel = parse_control_panel(
        {
            "mode": "1",
            "MI1": {
                "time": ["2026112510000020261125103000", "garbage"],
                "power": ["500", "20"],
            },
        }
    )

    assert len(panel.windows) == 1
    assert panel.windows[0].power == 500


def test_parse_control_panel_keeps_leftover_width_when_idle() -> None:
    """Test the width is read even though the leftover window is not reported."""
    panel = parse_control_panel(LAKE6_ACTIVE_PAYLOAD | {"mode": "0"})

    assert panel.active is False
    assert panel.windows == []
    assert panel.timestamp_width == 14


async def test_client_get_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a successful GET is decoded into the parsed device."""
    aioclient_mock.get(DEVICES_URL, json={"code": 200, "data": LAKE6_DEVICES_PAYLOAD})

    client = Lake6ApiClient(LAKE6_IP, async_get_clientsession(hass))
    device = await client.async_get_device()

    assert device.dev_id == LAKE6_DEV_ID


@pytest.mark.parametrize(
    ("body", "expected_code", "message"),
    [
        pytest.param({"code": 1002, "data": {}}, 1002, "data format error", id="code"),
        pytest.param({"data": {}}, None, "no numeric code", id="missing-code"),
        pytest.param({"code": 200, "data": []}, None, "no data object", id="no-data"),
    ],
)
async def test_client_get_device_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    body: dict[str, object],
    expected_code: int | None,
    message: str,
) -> None:
    """Test a broken answer is reported as Lake6ApiError."""
    aioclient_mock.get(DEVICES_URL, json=body)

    client = Lake6ApiClient(LAKE6_IP, async_get_clientsession(hass))
    with pytest.raises(Lake6ApiError, match=message) as err:
        await client.async_get_device()

    assert err.value.code == expected_code


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        pytest.param({"status": 500}, "HTTP 500", id="http-status"),
        pytest.param({"text": "<html>"}, "invalid JSON", id="invalid-json"),
        pytest.param({"json": ["data"]}, "non-object body", id="non-object"),
    ],
)
async def test_client_transport_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    kwargs: dict[str, object],
    message: str,
) -> None:
    """Test transport level failures are wrapped in Lake6ApiError."""
    aioclient_mock.get(DEVICES_URL, **kwargs)

    client = Lake6ApiClient(LAKE6_IP, async_get_clientsession(hass))
    with pytest.raises(Lake6ApiError, match=message):
        await client.async_get_device()


async def test_client_control_panel_message_fallback(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test /control-panels accepts a missing code when message says SUCCESS."""
    aioclient_mock.get(
        CONTROL_PANELS_URL, json={"message": "SUCCESS", "data": LAKE6_ACTIVE_PAYLOAD}
    )

    client = Lake6ApiClient(LAKE6_IP, async_get_clientsession(hass))
    panel = await client.async_get_control_panel()

    assert panel.active is True


async def test_client_control_panel_message_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a non-success message fails even though the code is optional."""
    aioclient_mock.get(CONTROL_PANELS_URL, json={"message": "FAIL", "data": {}})

    client = Lake6ApiClient(LAKE6_IP, async_get_clientsession(hass))
    with pytest.raises(Lake6ApiError, match="reported 'FAIL'"):
        await client.async_get_control_panel()


async def test_client_set_modes(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a mode write is posted and accepted."""
    aioclient_mock.post(MODES_URL, json={"code": 200})

    client = Lake6ApiClient(LAKE6_IP, async_get_clientsession(hass))
    await client.async_set_modes(eco="1")


async def test_client_set_control_panel(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a manual control write accepts the message-only envelope."""
    aioclient_mock.post(CONTROL_PANELS_URL, json={"message": "SUCCESS"})

    client = Lake6ApiClient(LAKE6_IP, async_get_clientsession(hass))
    await client.async_set_control_panel({"mode": "0", "MI1": {}})
