"""Test repairs for MQTT."""

from collections.abc import Awaitable, Callable, Coroutine
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from cryptography.x509.oid import NameOID
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)
from pytest_homeassistant.components.mqtt.common import (
    MOCK_NOTIFY_SUBENTRY_DATA_MULTI,
    async_fire_mqtt_message,
)
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.plugins import ClientSessionGenerator
from pytest_homeassistant.typing import MqttMockHAClientGenerator

from homeassistant.components.mqtt.const import (
    CONF_BROKER,
    CONF_CERTIFICATE_FILE,
    CONF_CLIENT_CERT,
    CONF_CLIENT_CERT_FILE,
    CONF_CLIENT_KEY,
    CONF_CLIENT_KEY_FILE,
    DOMAIN,
)
from homeassistant.components.mqtt.repairs import ISSUE_CLIENT_CERTIFICATE
from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import CONF_PROTOCOL, SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import parse_yaml


async def help_setup_yaml(hass: HomeAssistant, config: dict[str, str]) -> None:
    """Help to set up an exported MQTT device via YAML."""
    with patch(
        "homeassistant.config.load_yaml_config_file",
        return_value=parse_yaml(config["yaml"]),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()


async def help_setup_discovery(hass: HomeAssistant, config: dict[str, str]) -> None:
    """Help to set up an exported MQTT device via YAML."""
    async_fire_mqtt_message(
        hass, config["discovery_topic"], config["discovery_payload"]
    )
    await hass.async_block_till_done(wait_background_tasks=True)


async def help_export_config(
    hass: HomeAssistant, flow_id: str, flow_step: str
) -> dict[str, str]:
    """Help to export an MQTT device from an open subentry reconfigure flow."""
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {"next_step_id": "export"},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "export"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": flow_step},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == flow_step
    assert result["description_placeholders"] == {
        "url": "https://www.home-assistant.io/integrations/mqtt/"
    }

    # Copy the exported config suggested values for an export
    return {
        field: field.description["suggested_value"]
        for field in result["data_schema"].schema
    }


@pytest.mark.parametrize(
    "mqtt_config_subentries_data",
    [
        (
            ConfigSubentryData(
                data=MOCK_NOTIFY_SUBENTRY_DATA_MULTI,
                subentry_type="device",
                title="Mock subentry",
            ),
        )
    ],
)
@pytest.mark.parametrize(
    ("flow_step", "setup_helper", "translation_key"),
    [
        ("export_yaml", help_setup_yaml, "subentry_migration_yaml"),
        ("export_discovery", help_setup_discovery, "subentry_migration_discovery"),
    ],
)
async def test_subentry_reconfigure_export_settings(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
    flow_step: str,
    setup_helper: Coroutine[Any, Any, None],
    translation_key: str,
) -> None:
    """Test the subentry ConfigFlow YAML export with migration to YAML."""
    await mqtt_mock_entry()
    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry_id: str
    subentry: ConfigSubentry
    subentry_id, subentry = next(iter(config_entry.subentries.items()))
    result = await config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # assert we have a device for the subentry
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, subentry_id), config_entry.entry_id
    )
    assert device.config_subentry_id == subentry_id
    assert device is not None

    # assert we entity for all subentry components
    components = deepcopy(dict(subentry.data))["components"]
    assert len(components) == 2

    # assert menu options, we have the option to export
    assert result["menu_options"] == [
        "entity",
        "update_entity",
        "delete_entity",
        "device",
        "availability",
        "export",
    ]

    suggested_values_from_schema = await help_export_config(
        hass, result["flow_id"], flow_step
    )
    #  Try to set up the exported config with a changed device name
    events = async_capture_events(hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)
    await setup_helper(hass, suggested_values_from_schema)

    # Assert the subentry device was not effected by the exported configs
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, subentry_id), config_entry.entry_id
    )
    assert device.config_subentry_id == subentry_id
    assert device is not None

    # Assert a repair flow was created
    # This happens when the exported device identifier was detected
    # The subentry ID is used as device identifier
    assert len(events) == 1
    issue_id = events[0].data["issue_id"]
    repair_issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert repair_issue.translation_key == translation_key
    assert repair_issue.config_entry_id == config_entry.entry_id
    assert repair_issue.config_subentry_id == subentry_id

    client = await hass_client()

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"name": "Milk notifier"}
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, flow_id)
    assert data["type"] == "create_entry"

    # Assert the subentry is removed and no other entity has linked the device
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, subentry_id), config_entry.entry_id
    )
    assert device is None

    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(config_entry.subentries) == 0
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    #  Try to set up the exported config again
    events = async_capture_events(hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)
    await setup_helper(hass, suggested_values_from_schema)
    assert len(events) == 0

    # The MQTT device was now set up from the new source
    await hass.async_block_till_done(wait_background_tasks=True)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, subentry_id), config_entry.entry_id
    )
    assert device.config_subentry_id is None
    assert device is not None


def _generate_certificate(not_valid_after: datetime) -> tuple[bytes, bytes]:
    """Generate a self signed PEM encoded certificate and private key."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "mqtt-client")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        # Renewed certificates must already be valid when they are installed
        .not_valid_before(min(dt_util.utcnow(), not_valid_after - timedelta(days=90)))
        .not_valid_after(not_valid_after)
        .sign(key, hashes.SHA256())
    )
    return (
        certificate.public_bytes(Encoding.PEM),
        key.private_bytes(
            Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
        ),
    )


def _install_certificate(
    cert_dir: Path, not_valid_after: datetime
) -> tuple[bytes, bytes]:
    """Install a client certificate and private key file."""
    certificate, key = _generate_certificate(not_valid_after)
    (cert_dir / "client.crt").write_bytes(certificate)
    (cert_dir / "client.key").write_bytes(key)
    return certificate, key


def _certificate_file_data(cert_dir: Path) -> dict[str, Any]:
    """Return the entry data to load the client certificate from files."""
    return {
        CONF_CLIENT_CERT_FILE: str(cert_dir / "client.crt"),
        CONF_CLIENT_KEY_FILE: str(cert_dir / "client.key"),
    }


async def _async_setup_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    data: dict[str, Any],
) -> MockConfigEntry:
    """Set up the MQTT entry with the client certificate settings."""
    entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(
        entry, data={CONF_BROKER: "mock-broker", CONF_PROTOCOL: "5"} | data
    )
    await mqtt_mock_entry()
    return entry


async def _async_advance_one_day(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance the time to trigger the daily certificate check."""
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({}, id="no_client_certificate"),
        pytest.param(
            {CONF_CLIENT_CERT: "invalid", CONF_CLIENT_KEY: "invalid"},
            id="invalid_uploaded_certificate",
        ),
        pytest.param(
            {
                CONF_CLIENT_CERT_FILE: "/ssl/mqtt/client.crt",
                CONF_CLIENT_KEY_FILE: "/ssl/mqtt/client.key",
            },
            id="missing_certificate_file",
        ),
    ],
)
async def test_no_loaded_client_certificate(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    issue_registry: ir.IssueRegistry,
    data: dict[str, Any],
) -> None:
    """Test a stale issue is removed when no client certificate is loaded."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_CLIENT_CERTIFICATE,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="client_certificate_expiring",
        translation_placeholders={"broker": "mock-broker", "expiry": "2026-11-04"},
    )
    await _async_setup_entry(hass, mqtt_mock_entry, data)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_CLIENT_CERTIFICATE) is None


@pytest.mark.parametrize(
    ("valid_days", "severity"),
    [
        pytest.param(10, ir.IssueSeverity.WARNING, id="expires_soon"),
        pytest.param(-1, ir.IssueSeverity.ERROR, id="expired"),
    ],
)
async def test_uploaded_client_certificate_expiring(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    issue_registry: ir.IssueRegistry,
    valid_days: int,
    severity: ir.IssueSeverity,
) -> None:
    """Test an issue is created when an uploaded client certificate expires soon."""
    expiry = dt_util.utcnow() + timedelta(days=valid_days)
    certificate, key = _generate_certificate(expiry)
    entry = await _async_setup_entry(
        hass,
        mqtt_mock_entry,
        {CONF_CLIENT_CERT: certificate.decode(), CONF_CLIENT_KEY: key.decode()},
    )

    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_CLIENT_CERTIFICATE)
    assert issue is not None
    assert issue.translation_key == "client_certificate_expiring"
    assert issue.is_fixable is False
    assert issue.severity is severity
    assert issue.config_entry_id == entry.entry_id
    assert issue.translation_placeholders == {
        "broker": "mock-broker",
        "expiry": expiry.date().isoformat(),
    }

    # The issue is removed when the entry is unloaded
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_CLIENT_CERTIFICATE) is None


async def test_client_certificate_file_expiring(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    tmp_path: Path,
) -> None:
    """Test the daily check creates an issue when the certificate expires soon."""
    expiry = dt_util.utcnow() + timedelta(days=31, hours=12)
    await hass.async_add_executor_job(_install_certificate, tmp_path, expiry)
    await _async_setup_entry(hass, mqtt_mock_entry, _certificate_file_data(tmp_path))
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_CLIENT_CERTIFICATE) is None

    await _async_advance_one_day(hass, freezer)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_CLIENT_CERTIFICATE) is None

    # The certificate expires within 30 days, but was not renewed
    await _async_advance_one_day(hass, freezer)
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_CLIENT_CERTIFICATE)
    assert issue is not None
    assert issue.translation_key == "client_certificate_file_expiring"
    assert issue.is_fixable is False
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {
        "broker": "mock-broker",
        "expiry": expiry.date().isoformat(),
        "client_cert_file": str(tmp_path / "client.crt"),
    }


def _install_invalid_certificate(cert_dir: Path) -> None:
    """Install an invalid client certificate file."""
    (cert_dir / "client.crt").write_text("invalid")


def _install_invalid_key(cert_dir: Path) -> None:
    """Install an invalid private key file."""
    (cert_dir / "client.key").write_text("invalid")


def _install_mismatching_key(cert_dir: Path) -> None:
    """Install a private key that does not match the client certificate."""
    _, key = _generate_certificate(dt_util.utcnow() + timedelta(days=90))
    (cert_dir / "client.key").write_bytes(key)


def _install_invalid_ca_certificate(cert_dir: Path) -> None:
    """Install an invalid CA certificate file."""
    (cert_dir / "ca.crt").write_text("invalid")


@pytest.mark.parametrize(
    ("install_invalid_files", "translation_key", "file_placeholders"),
    [
        pytest.param(
            _install_invalid_certificate,
            "client_certificate_file_invalid",
            {},
            id="invalid_certificate",
        ),
        pytest.param(
            _install_invalid_key,
            "client_key_file_invalid",
            {"client_key_file": "client.key"},
            id="invalid_key",
        ),
        pytest.param(
            _install_mismatching_key,
            "client_certificate_key_mismatch",
            {"client_key_file": "client.key"},
            id="mismatching_key",
        ),
        pytest.param(
            _install_invalid_ca_certificate,
            "ca_certificate_file_invalid",
            {"ca_cert_file": "ca.crt"},
            id="invalid_ca_certificate",
        ),
    ],
)
async def test_installed_certificate_files_invalid(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    tmp_path: Path,
    install_invalid_files: Callable[[Path], None],
    translation_key: str,
    file_placeholders: dict[str, str],
) -> None:
    """Test an issue is created when invalid certificate files are installed."""
    expiry = dt_util.utcnow() + timedelta(days=10)
    certificate, _ = await hass.async_add_executor_job(
        _install_certificate, tmp_path, expiry
    )
    # Use the client certificate as a valid CA certificate
    await hass.async_add_executor_job((tmp_path / "ca.crt").write_bytes, certificate)
    await _async_setup_entry(
        hass,
        mqtt_mock_entry,
        _certificate_file_data(tmp_path)
        | {CONF_CERTIFICATE_FILE: str(tmp_path / "ca.crt")},
    )
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_CLIENT_CERTIFICATE)
    assert issue is not None
    assert issue.translation_key == "client_certificate_file_expiring"

    await hass.async_add_executor_job(install_invalid_files, tmp_path)
    await _async_advance_one_day(hass, freezer)
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_CLIENT_CERTIFICATE)
    assert issue is not None
    assert issue.translation_key == translation_key
    assert issue.is_fixable is False
    assert issue.translation_placeholders == {
        "broker": "mock-broker",
        "expiry": expiry.date().isoformat(),
        "client_cert_file": str(tmp_path / "client.crt"),
    } | {key: str(tmp_path / file) for key, file in file_placeholders.items()}


async def test_renewed_client_certificate_reload(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    tmp_path: Path,
) -> None:
    """Test the repair flow reloads MQTT when a renewed certificate is installed."""
    assert await async_setup_component(hass, "repairs", {})
    start = dt_util.utcnow()
    expiry = start + timedelta(days=10)
    await hass.async_add_executor_job(_install_certificate, tmp_path, expiry)
    entry = await _async_setup_entry(
        hass, mqtt_mock_entry, _certificate_file_data(tmp_path)
    )

    await hass.async_add_executor_job(
        _install_certificate, tmp_path, expiry + timedelta(days=90)
    )
    await _async_advance_one_day(hass, freezer)
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_CLIENT_CERTIFICATE)
    assert issue is not None
    assert issue.translation_key == "client_certificate_renewed"
    assert issue.is_fixable is True
    assert issue.severity is ir.IssueSeverity.WARNING

    # Move back in time, so the access token of the test client is still valid
    freezer.move_to(start)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_CLIENT_CERTIFICATE)
    assert data["step_id"] == "confirm"
    assert data["description_placeholders"] == {
        "broker": "mock-broker",
        "expiry": expiry.date().isoformat(),
        "client_cert_file": str(tmp_path / "client.crt"),
    }

    with patch.object(
        hass.config_entries,
        "async_schedule_reload",
        wraps=hass.config_entries.async_schedule_reload,
    ) as mock_reload:
        data = await process_repair_fix_flow(client, data["flow_id"])
        assert data["type"] == "create_entry"
        await hass.async_block_till_done(wait_background_tasks=True)
    mock_reload.assert_called_once_with(entry.entry_id)

    # The renewed certificate is loaded after the reload
    assert entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_CLIENT_CERTIFICATE) is None


async def _remove_subentry(
    hass: HomeAssistant, config_entry: MockConfigEntry, subentry_id: str
) -> None:
    assert hass.config_entries.async_remove_subentry(config_entry, subentry_id)


async def _remove_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, subentry_id: str
) -> None:
    await hass.config_entries.async_remove(config_entry.entry_id)


@pytest.mark.parametrize(
    "mqtt_config_subentries_data",
    [
        (
            ConfigSubentryData(
                data=MOCK_NOTIFY_SUBENTRY_DATA_MULTI,
                subentry_type="device",
                title="Mock subentry",
            ),
        )
    ],
)
@pytest.mark.parametrize(
    ("flow_step", "setup_helper"),
    [
        pytest.param("export_yaml", help_setup_yaml, id="yaml"),
        pytest.param("export_discovery", help_setup_discovery, id="discovery"),
    ],
)
@pytest.mark.parametrize(
    "remove",
    [
        pytest.param(_remove_subentry, id="remove_subentry"),
        pytest.param(_remove_config_entry, id="remove_config_entry"),
    ],
)
async def test_subentry_migration_issue_removed(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    issue_registry: ir.IssueRegistry,
    flow_step: str,
    setup_helper: Callable[[HomeAssistant, dict[str, str]], Awaitable[None]],
    remove: Callable[[HomeAssistant, MockConfigEntry, str], Awaitable[None]],
) -> None:
    """Test the migration issue is removed with its subentry or config entry."""
    await mqtt_mock_entry()
    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry_id = next(iter(config_entry.subentries))
    result = await config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    suggested_values_from_schema = await help_export_config(
        hass, result["flow_id"], flow_step
    )
    await setup_helper(hass, suggested_values_from_schema)

    # The subentry ID is used as issue ID
    assert (issue := issue_registry.async_get_issue(DOMAIN, subentry_id))
    assert issue.config_entry_id == config_entry.entry_id
    assert issue.config_subentry_id == subentry_id

    await remove(hass, config_entry, subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert issue_registry.async_get_issue(DOMAIN, subentry_id) is None
