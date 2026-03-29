"""Unit tests for the config flow and options flow of the OPNsense integration.

Tests include URL parsing/validation, exception mapping for user input,
and options flow behaviors such as device tracker handling.
"""

import importlib
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from yarl import URL

from homeassistant.core import HomeAssistant

cf_mod = importlib.import_module("homeassistant.components.opnsense.config_flow")


def test_mac_and_ip_and_cleanse() -> None:
    """Validate MAC/IP helpers and cleanse sensitive data."""
    assert cf_mod.is_valid_mac_address("aa:bb:cc:dd:ee:ff")
    assert cf_mod.is_valid_mac_address("AA-BB-CC-DD-EE-FF")
    assert cf_mod.normalize_mac_address("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"
    assert not cf_mod.is_valid_mac_address("not-a-mac")

    # IP validation
    assert cf_mod.is_ip_address("192.168.1.1")
    assert not cf_mod.is_ip_address("not-an-ip")

    # cleanse sensitive data
    msg = "user=admin&pass=secret"
    out = cf_mod.cleanse_sensitive_data(msg, ["secret"])
    assert "[redacted]" in out
    assert "secret" not in out


def test_device_tracking_mode_helper() -> None:
    """Map stored devices to the expected UI tracking mode."""
    assert (
        cf_mod._get_device_tracking_mode(False, ["aa:bb:cc:dd:ee:ff"])
        == cf_mod.DEVICE_TRACKING_MODE_DISABLED
    )
    assert cf_mod._get_device_tracking_mode(True, []) == cf_mod.DEVICE_TRACKING_MODE_ALL
    assert (
        cf_mod._get_device_tracking_mode(True, None) == cf_mod.DEVICE_TRACKING_MODE_ALL
    )
    assert cf_mod._get_device_tracking_mode(True, ["aa:bb:cc:dd:ee:ff"]) == (
        cf_mod.DEVICE_TRACKING_MODE_SELECTED
    )


def test_parse_and_merge_manual_devices() -> None:
    """Parse mixed separators and deduplicate MAC addresses in order."""
    parsed = cf_mod._parse_manual_devices(
        "AA-BB-CC-DD-EE-FF,\n11:22:33:44:55:66\ninvalid\naa:bb:cc:dd:ee:ff"
    )
    assert parsed == [
        "aa:bb:cc:dd:ee:ff",
        "11:22:33:44:55:66",
        "aa:bb:cc:dd:ee:ff",
    ]
    assert cf_mod._merge_selected_devices(
        ["11:22:33:44:55:66", "aa-bb-cc-dd-ee-ff"],
        parsed,
    ) == [
        "11:22:33:44:55:66",
        "aa:bb:cc:dd:ee:ff",
    ]


def test_device_entry_sort_key_numeric_ip_sorting() -> None:
    """Sort key should use numeric IP ordering when an IP is available."""
    ip_by_mac = {
        "aa:bb:cc:dd:ee:ff": "10.0.0.5",
        "11:22:33:44:55:66": "",
        "22:33:44:55:66:77": "192.168.1.2",
        "33:44:55:66:77:88": "192.168.1.10",
    }
    ip_key = cf_mod._device_entry_sort_key(
        "aa:bb:cc:dd:ee:ff",
        "host-a [10.0.0.5 | aa:bb:cc:dd:ee:ff]",
        ip_by_mac,
    )
    label_key = cf_mod._device_entry_sort_key(
        "11:22:33:44:55:66",
        "host-b [11:22:33:44:55:66]",
        ip_by_mac,
    )
    subnet_key_2 = cf_mod._device_entry_sort_key(
        "22:33:44:55:66:77",
        "host-c [192.168.1.2 | 22:33:44:55:66:77]",
        ip_by_mac,
    )
    subnet_key_10 = cf_mod._device_entry_sort_key(
        "33:44:55:66:77:88",
        "host-d [192.168.1.10 | 33:44:55:66:77:88]",
        ip_by_mac,
    )
    assert ip_key == (1, (4, int(cf_mod.ipaddress.ip_address("10.0.0.5"))))
    assert label_key == (2, "host-b [11:22:33:44:55:66]")
    assert subnet_key_2 < subnet_key_10


@pytest.mark.asyncio
async def test_clean_and_parse_url_success_and_failure() -> None:
    """Clean and parse URL, fix missing scheme and handle invalid URL."""
    ui = {cf_mod.CONF_URL: "router.example"}
    await cf_mod._clean_and_parse_url(ui)
    assert ui[cf_mod.CONF_URL] == "https://router.example"

    # invalid netloc -> raise InvalidURL
    with pytest.raises(cf_mod.InvalidURL):
        await cf_mod._clean_and_parse_url({cf_mod.CONF_URL: ""})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc_key", "expected"),
    [
        ("below_min", "below_min_firmware"),
        ("unknown_fw", "unknown_firmware"),
        ("missing_id", "missing_device_unique_id"),
        ("invalid_url", "invalid_url_format"),
        ("client_connector_ssl", "cannot_connect_ssl"),
        ("resp_401", "invalid_auth"),
        ("resp_403", "privilege_missing"),
        ("resp_500", "cannot_connect"),
        ("protocol_307", "url_redirect"),
        ("too_many_redirects", "url_redirect"),
        ("timeout", "connect_timeout"),
        ("server_timeout", "connect_timeout"),
        ("os_ssl", "privilege_missing"),
        ("os_timed_out", "connect_timeout"),
        ("os_ssl_handshake", "cannot_connect_ssl"),
        ("os_unknown", "unknown"),
    ],
)
async def test_validate_input_exception_mapping(
    monkeypatch: pytest.MonkeyPatch, exc_key: str, expected: str
) -> None:
    """Ensure validate_input maps various exceptions to the expected error code."""

    # Build exception object lazily to avoid constructor issues at collection time
    if exc_key == "below_min":
        exc = cf_mod.BelowMinFirmware()
    elif exc_key == "unknown_fw":
        exc = cf_mod.UnknownFirmware()
    elif exc_key == "missing_id":
        exc = cf_mod.MissingDeviceUniqueID("x")
    elif exc_key == "invalid_url":
        exc = aiohttp.InvalidURL("u")
    elif exc_key == "client_connector_ssl":
        # Simulate an SSL-related client error that maps to "cannot_connect_ssl".
        # ClientSSLError (and its base ClientConnectorError) require a connection
        # key and an underlying os_error; provide a minimal connector-like
        # object and an OSError to construct the exception instance.
        class Conn:
            host = "host.example"
            port = 443
            ssl = None

        exc = aiohttp.ClientSSLError(Conn(), OSError("ssl error"))
    elif exc_key in ("resp_401", "resp_403", "resp_500"):
        status = 401 if exc_key == "resp_401" else 403 if exc_key == "resp_403" else 500

        # Provide minimal request_info with a real_url to satisfy logging/str()
        class RI:
            real_url = URL("http://localhost")

        exc = aiohttp.ClientResponseError(
            request_info=RI(), history=(), status=status, message="m"
        )
    elif exc_key == "protocol_307":
        exc = aiohttp.RedirectClientError("307 Temporary Redirect")
    elif exc_key == "too_many_redirects":

        class RI:
            real_url = URL("http://localhost")

        exc = aiohttp.TooManyRedirects(request_info=RI(), history=())
    elif exc_key == "timeout":
        exc = TimeoutError("t")
    elif exc_key == "server_timeout":
        exc = aiohttp.ServerTimeoutError("t")
    elif exc_key == "os_ssl":
        exc = OSError("unsupported XML-RPC protocol")
    elif exc_key == "os_timed_out":
        exc = OSError("timed out")
    elif exc_key == "os_ssl_handshake":
        exc = OSError("SSL: handshake")
    else:
        exc = OSError("unknown")

    async def _raiser(*args, **kwargs):
        raise exc

    monkeypatch.setattr(cf_mod, "_handle_user_input", _raiser)
    errors = {}
    res = await cf_mod.validate_input(
        hass=MagicMock(), user_input={}, errors=errors, config_step="user"
    )
    assert res.get("base") == expected


@pytest.mark.asyncio
async def test_validate_input_client_error_maps_to_cannot_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generic aiohttp and socket errors should map to cannot_connect."""

    async def _raise_client_error(*args, **kwargs):
        raise aiohttp.ClientError("boom")

    monkeypatch.setattr(cf_mod, "_handle_user_input", _raise_client_error)
    errors = await cf_mod.validate_input(
        hass=MagicMock(), user_input={}, errors={}, config_step="user"
    )
    assert errors["base"] == "cannot_connect"

    async def _raise_socket_error(*args, **kwargs):
        raise cf_mod.socket.gaierror("boom")

    monkeypatch.setattr(cf_mod, "_handle_user_input", _raise_socket_error)
    errors = await cf_mod.validate_input(
        hass=MagicMock(), user_input={}, errors={}, config_step="user"
    )
    assert errors["base"] == "cannot_connect"


def test_validate_firmware_version_raises() -> None:
    """_validate_firmware_version should raise BelowMinFirmware for old versions."""
    # pick an obviously old version
    with pytest.raises(cf_mod.BelowMinFirmware):
        cf_mod._validate_firmware_version("1.0")


def test_log_and_set_error_sets_base(caplog: pytest.LogCaptureFixture) -> None:
    """_log_and_set_error should log the message and set errors['base']."""
    errors = {}
    cf_mod._log_and_set_error(errors=errors, key="test_key", message="an msg")
    assert errors.get("base") == "test_key"
    assert "an msg" in caplog.text


@pytest.mark.asyncio
async def test_get_dt_entries_sorts_and_includes_selected(
    monkeypatch: pytest.MonkeyPatch, fake_client
) -> None:
    """Ensure _get_dt_entries returns selected devices first and ARP entries sorted by IP."""

    # Create a client class via fixture and attach a get_arp_table implementation
    client_cls = fake_client()

    async def _get_arp_table(self, resolve_hostnames=True):
        return [
            {"mac": "aa:bb:cc:00:00:01", "hostname": "hostb", "ip": "192.168.1.20"},
            {"mac": "aa:bb:cc:00:00:03", "hostname": "hostc", "ip": "192.168.1.100"},
            {"mac": "11:22:33:44:55:66", "hostname": "", "ip": "10.0.0.5"},
            {"mac": "bb:cc:dd:00:00:02", "hostname": "hosta", "ip": "192.168.1.10"},
        ]

    setattr(client_cls, "get_arp_table", _get_arp_table)
    monkeypatch.setattr(cf_mod, "OPNsenseClient", client_cls)

    # Patch async_create_clientsession on the module under test to avoid real network I/O
    def _fake_create_clientsession(*args, **kwargs):
        return MagicMock()

    monkeypatch.setattr(
        cf_mod, "async_create_clientsession", _fake_create_clientsession
    )

    hass = MagicMock()
    config = {
        cf_mod.CONF_URL: "https://x",
        cf_mod.CONF_USERNAME: "u",
        cf_mod.CONF_PASSWORD: "p",
    }
    selected = ["aa:bb:cc:00:00:01"]
    res = await cf_mod._get_dt_entries(
        hass=hass, config=config, selected_devices=selected
    )

    # ensure selected device is present and IP-based entries are present
    keys = list(res.keys())
    assert "aa:bb:cc:00:00:01" in keys
    assert "11:22:33:44:55:66" in keys
    # Detected entries are sorted numerically by IP (10.0.0.5 before 192.168.1.10 < 192.168.1.20)
    vals = list(res.values())
    assert vals.index("10.0.0.5 [11:22:33:44:55:66]") < vals.index(
        "hosta [192.168.1.10 | bb:cc:dd:00:00:02]"
    )
    assert vals.index("hosta [192.168.1.10 | bb:cc:dd:00:00:02]") < vals.index(
        "hostb [192.168.1.20 | aa:bb:cc:00:00:01]"
    )
    assert vals.index("hostb [192.168.1.20 | aa:bb:cc:00:00:01]") < vals.index(
        "hostc [192.168.1.100 | aa:bb:cc:00:00:03]"
    )


@pytest.mark.asyncio
async def test_get_dt_entries_preserves_missing_selected_devices(
    monkeypatch: pytest.MonkeyPatch, fake_client
) -> None:
    """Selected MACs missing from ARP stay available with a fallback label."""

    client_cls = fake_client()

    async def _get_arp_table(self, resolve_hostnames=True):
        return [{"mac": "11:22:33:44:55:66", "hostname": "", "ip": "10.0.0.5"}]

    setattr(client_cls, "get_arp_table", _get_arp_table)
    monkeypatch.setattr(cf_mod, "OPNsenseClient", client_cls)
    monkeypatch.setattr(
        cf_mod, "async_create_clientsession", lambda *a, **k: MagicMock()
    )

    res = await cf_mod._get_dt_entries(
        hass=MagicMock(),
        config={
            cf_mod.CONF_URL: "https://x",
            cf_mod.CONF_USERNAME: "u",
            cf_mod.CONF_PASSWORD: "p",
        },
        selected_devices=["AA-BB-CC-DD-EE-FF"],
    )
    assert res["aa:bb:cc:dd:ee:ff"] == "Not currently detected [aa:bb:cc:dd:ee:ff]"


def test_config_flow_helper_guard_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover MAC parsing and device-label fallback branches."""
    assert cf_mod.normalize_mac_address(123) is None
    assert cf_mod._parse_manual_devices(None) == []
    assert cf_mod._build_selected_device_entries(
        ["not-a-mac", "AA-BB-CC-DD-EE-FF"]
    ) == {"aa:bb:cc:dd:ee:ff": "Not currently detected [aa:bb:cc:dd:ee:ff]"}
    assert (
        cf_mod._format_detected_device_label(
            {"mac": "AA-BB-CC-DD-EE-FF", "hostname": ""}
        )
        == "aa:bb:cc:dd:ee:ff [aa:bb:cc:dd:ee:ff]"
    )
    assert (
        cf_mod._format_detected_device_label(
            {
                "mac": "aa:bb:cc:dd:ee:ff",
                "ip": "192.168.1.10",
                "manufacturer": "Netgate",
            }
        )
        == "192.168.1.10 [Netgate | aa:bb:cc:dd:ee:ff]"
    )

    monkeypatch.setattr(
        cf_mod.re, "split", lambda *args, **kwargs: [123, "AA-BB-CC-DD-EE-FF"]
    )
    assert cf_mod._parse_manual_devices("ignored") == ["aa:bb:cc:dd:ee:ff"]


def test_build_user_input_and_granular_and_options_schemas_defaults() -> None:
    """Verify the schema builders accept empty input and return defaults where applicable."""
    uis = None
    # user input schema should provide keys and defaults
    schema = cf_mod._build_user_input_schema(user_input=uis)
    validated = schema({})
    assert cf_mod.CONF_URL in validated

    # granular sync schema
    gschema = cf_mod._build_granular_sync_schema(user_input=None)
    gvalidated = gschema({})
    # every granular item should be present (defaults applied)
    for item in cf_mod.GRANULAR_SYNC_ITEMS:
        assert item in gvalidated

    # options init schema: test clamping/coercion for scan interval
    oschema = cf_mod._build_options_init_schema(user_input=None)
    out = oschema({})
    assert cf_mod.CONF_SCAN_INTERVAL in out
    assert cf_mod.CONF_DEVICE_TRACKING_MODE in out


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (5, 10),  # below minimum -> clamped to 10
        (150, 150),  # within range -> unchanged
        (1000, 300),  # above maximum -> clamped to 300
    ],
)
def test_options_scan_interval_clamp(input_value: int, expected: int) -> None:
    """_build_options_init_schema should clamp CONF_SCAN_INTERVAL to min/max values."""
    oschema = cf_mod._build_options_init_schema(user_input=None)
    # pass a dict with the scan interval set to the test value
    validated = oschema({cf_mod.CONF_SCAN_INTERVAL: input_value})
    assert validated.get(cf_mod.CONF_SCAN_INTERVAL) == expected


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (-10, 0),  # below minimum -> clamped to 0
        (300, 300),  # within range -> unchanged
        (1200, 1200),  # within new range (20 minutes) -> unchanged
        (3600, 3600),  # at maximum (1 hour) -> unchanged
        (5000, 3600),  # above maximum -> clamped to 3600
    ],
)
def test_options_device_tracker_consider_home_clamp(
    input_value: int, expected: int
) -> None:
    """_build_options_init_schema should clamp CONF_DEVICE_TRACKER_CONSIDER_HOME to min/max values."""
    oschema = cf_mod._build_options_init_schema(user_input=None)
    # pass a dict with the consider_home value set to the test value
    validated = oschema({cf_mod.CONF_DEVICE_TRACKER_CONSIDER_HOME: input_value})
    assert validated.get(cf_mod.CONF_DEVICE_TRACKER_CONSIDER_HOME) == expected


def test_async_get_options_flow_returns_options_flow() -> None:
    """async_get_options_flow should return an OPNsenseOptionsFlow instance."""
    cfg = MagicMock()
    res = cf_mod.OPNsenseConfigFlow.async_get_options_flow(cfg)
    assert isinstance(res, cf_mod.OPNsenseOptionsFlow)


@pytest.mark.asyncio
async def test_options_flow_init_with_user_triggers_update() -> None:
    """Submitting user input to async_step_init should update entry and create entry."""
    cfg = MagicMock()
    cfg.data = {
        cf_mod.CONF_URL: "https://x",
        cf_mod.CONF_USERNAME: "u",
        cf_mod.CONF_PASSWORD: "p",
    }
    cfg.options = {cf_mod.CONF_DEVICE_TRACKER_ENABLED: False}

    flow = cf_mod.OPNsenseOptionsFlow(cfg)
    flow.hass = MagicMock()
    flow.hass.config_entries = MagicMock()
    flow.hass.config_entries.async_update_entry = MagicMock()
    # set a handler so flow._config_entry_id property is available during the test
    flow.handler = "opnsense"
    # ensure async_get_known_entry returns our cfg when accessed
    flow.hass.config_entries.async_get_known_entry = MagicMock(return_value=cfg)

    # populate internals to avoid Home Assistant property lookups in this unit test
    flow._config = dict(cfg.data)
    flow._options = dict(cfg.options)

    user_input = {cf_mod.CONF_SCAN_INTERVAL: 30}
    res = await flow.async_step_init(user_input=user_input)

    # should have called update_entry and returned create_entry
    flow.hass.config_entries.async_update_entry.assert_called()
    assert res["type"] == "create_entry"
    assert flow._options.get(cf_mod.CONF_SCAN_INTERVAL) == 30


@pytest.mark.asyncio
async def test_options_flow_granular_sync_calls_validate_and_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """async_step_granular_sync should call validate_input and update entry when no errors."""
    cfg = MagicMock()
    cfg.data = {
        cf_mod.CONF_URL: "https://x",
        cf_mod.CONF_USERNAME: "u",
        cf_mod.CONF_PASSWORD: "p",
    }
    cfg.options = {cf_mod.CONF_DEVICE_TRACKER_ENABLED: False}

    flow = cf_mod.OPNsenseOptionsFlow(cfg)
    flow.hass = MagicMock()
    flow.hass.config_entries = MagicMock()
    flow.hass.config_entries.async_update_entry = MagicMock()

    # monkeypatch validate_input to return no errors
    async def fake_validate(
        hass: HomeAssistant | None, user_input, errors, **kwargs
    ) -> dict:
        return {}

    monkeypatch.setattr(cf_mod, "validate_input", fake_validate)

    # use an actual granular sync key present in the module
    gkey = next(iter(cf_mod.GRANULAR_SYNC_ITEMS))
    # populate internals so the flow method doesn't access Home Assistant internals
    flow._config = dict(cfg.data)
    flow._options = dict(cfg.options)
    user_input = {gkey: True}
    # set a handler and make async_get_known_entry return our cfg so the flow can access
    # config_entry and options during unit tests without Home Assistant internals.
    flow.handler = "opnsense"
    flow.hass.config_entries.async_get_known_entry = MagicMock(return_value=cfg)
    res = await flow.async_step_granular_sync(user_input=user_input)
    flow.hass.config_entries.async_update_entry.assert_called()
    assert res["type"] == "create_entry"


@pytest.mark.asyncio
async def test_async_step_import_preserves_import_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """YAML import should create a config entry with the supplied options payload."""
    flow = cf_mod.OPNsenseConfigFlow()
    flow.hass = MagicMock()

    async def _fake_validate_input(
        hass: HomeAssistant | None, user_input, config_step, errors, expected_id=None
    ) -> dict:
        return {}

    async def _noop_unique_id(*args, **kwargs):
        return None

    monkeypatch.setattr(cf_mod, "validate_input", _fake_validate_input)
    flow.async_set_unique_id = _noop_unique_id
    flow._abort_if_unique_id_configured = lambda: None

    user_input = {
        cf_mod.CONF_NAME: "Imported Router",
        cf_mod.CONF_URL: "https://router.example",
        cf_mod.CONF_USERNAME: "api-key",
        cf_mod.CONF_PASSWORD: "api-secret",
        cf_mod.CONF_DEVICE_UNIQUE_ID: "router-id",
        cf_mod.IMPORT_OPTIONS_KEY: {
            cf_mod.CONF_DEVICE_TRACKER_ENABLED: True,
            cf_mod.CONF_DEVICES: [],
        },
    }

    result = await flow.async_step_import(dict(user_input))
    assert result["type"] == "create_entry"
    assert result["title"] == "Imported Router"
    assert result["options"][cf_mod.CONF_DEVICE_TRACKER_ENABLED] is True
    assert result["options"][cf_mod.CONF_DEVICES] == []


@pytest.mark.asyncio
async def test_handle_user_input_unknown_firmware_and_missing_device_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_handle_user_input should translate firmware parse failures and missing ids."""

    fake_client = MagicMock()
    fake_client.get_host_firmware_version = AsyncMock(return_value="not-a-version")
    fake_client.get_system_info = AsyncMock(return_value={})
    fake_client.get_device_unique_id = AsyncMock(return_value=None)

    async def _fake_clean(user_input):
        user_input[cf_mod.CONF_URL] = "https://router.example"

    monkeypatch.setattr(cf_mod, "_clean_and_parse_url", _fake_clean)
    monkeypatch.setattr(cf_mod, "_get_client", AsyncMock(return_value=fake_client))
    monkeypatch.setattr(
        cf_mod, "_validate_firmware_version", MagicMock(side_effect=ValueError)
    )

    with pytest.raises(cf_mod.UnknownFirmware):
        await cf_mod._handle_user_input(
            hass=MagicMock(),
            user_input={
                cf_mod.CONF_URL: "router.example",
                cf_mod.CONF_USERNAME: "u",
                cf_mod.CONF_PASSWORD: "p",
            },
            config_step="user",
        )

    monkeypatch.setattr(cf_mod, "_validate_firmware_version", lambda version: None)
    user_input = {
        cf_mod.CONF_URL: "router.example",
        cf_mod.CONF_USERNAME: "u",
        cf_mod.CONF_PASSWORD: "p",
    }
    with pytest.raises(cf_mod.MissingDeviceUniqueID):
        await cf_mod._handle_user_input(
            hass=MagicMock(),
            user_input=user_input,
            config_step="user",
        )
    assert user_input[cf_mod.CONF_NAME] == "OPNsense"


@pytest.mark.asyncio
async def test_get_dt_entries_skips_empty_mac_and_handles_empty_arp(
    monkeypatch: pytest.MonkeyPatch, fake_client
) -> None:
    """_get_dt_entries should skip empty MACs and return selected entries when ARP is empty."""
    client_cls = fake_client()

    async def _get_arp_table_empty_mac(self, resolve_hostnames=True):
        return [{"mac": "", "ip": "192.168.1.10"}, {"mac": "AA-BB-CC-DD-EE-FF"}]

    setattr(client_cls, "get_arp_table", _get_arp_table_empty_mac)
    monkeypatch.setattr(cf_mod, "OPNsenseClient", client_cls)
    monkeypatch.setattr(
        cf_mod, "async_create_clientsession", lambda *a, **k: MagicMock()
    )

    result = await cf_mod._get_dt_entries(
        hass=MagicMock(),
        config={
            cf_mod.CONF_URL: "https://x",
            cf_mod.CONF_USERNAME: "u",
            cf_mod.CONF_PASSWORD: "p",
        },
        selected_devices=[],
    )
    assert list(result) == ["aa:bb:cc:dd:ee:ff"]

    async def _get_arp_table_empty(self, resolve_hostnames=True):
        return []

    setattr(client_cls, "get_arp_table", _get_arp_table_empty)
    result = await cf_mod._get_dt_entries(
        hass=MagicMock(),
        config={
            cf_mod.CONF_URL: "https://x",
            cf_mod.CONF_USERNAME: "u",
            cf_mod.CONF_PASSWORD: "p",
        },
        selected_devices=["AA-BB-CC-DD-EE-FF"],
    )
    assert result == {"aa:bb:cc:dd:ee:ff": "Not currently detected [aa:bb:cc:dd:ee:ff]"}


@pytest.mark.asyncio
async def test_async_step_reauth_confirm_updates_existing_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reauth should validate new credentials and request a reload of the existing entry."""
    flow = cf_mod.OPNsenseConfigFlow()
    flow.hass = MagicMock()

    async def _fake_validate_input(
        hass: HomeAssistant | None, user_input, config_step, errors, expected_id=None
    ) -> dict:
        return {}

    reauth_entry = MagicMock()
    reauth_entry.data = {
        cf_mod.CONF_NAME: "Router",
        cf_mod.CONF_URL: "https://router.example",
        cf_mod.CONF_USERNAME: "old-user",
        cf_mod.CONF_PASSWORD: "old-pass",
        cf_mod.CONF_DEVICE_UNIQUE_ID: "router-id",
    }

    monkeypatch.setattr(cf_mod, "validate_input", _fake_validate_input)
    flow._get_reauth_entry = lambda: reauth_entry

    expected_result = {"type": "abort", "reason": "reauth_successful"}
    flow.async_update_reload_and_abort = MagicMock(return_value=expected_result)

    result = await flow.async_step_reauth_confirm(
        user_input={
            cf_mod.CONF_URL: "https://router.example",
            cf_mod.CONF_USERNAME: "new-user",
            cf_mod.CONF_PASSWORD: "new-pass",
            cf_mod.CONF_VERIFY_SSL: True,
        }
    )

    assert result == expected_result
    flow.async_update_reload_and_abort.assert_called_once()
    assert flow.async_update_reload_and_abort.call_args.kwargs["entry"] is reauth_entry
    assert (
        flow.async_update_reload_and_abort.call_args.kwargs["data_updates"][
            cf_mod.CONF_USERNAME
        ]
        == "new-user"
    )


@pytest.mark.asyncio
async def test_async_step_user_and_reconfigure_show_forms(
    make_config_entry,
) -> None:
    """Initial and reconfigure steps should render forms before submission."""
    flow = cf_mod.OPNsenseConfigFlow()
    flow.hass = MagicMock()

    result = await flow.async_step_user(user_input={})
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["description_placeholders"]["firmware"] == "Unknown"

    reconfigure_entry = make_config_entry(
        data={
            cf_mod.CONF_NAME: "Router",
            cf_mod.CONF_URL: "https://router.example",
            cf_mod.CONF_USERNAME: "user",
            cf_mod.CONF_PASSWORD: "pass",
            cf_mod.CONF_DEVICE_UNIQUE_ID: "router-id",
        }
    )
    flow._get_reconfigure_entry = lambda: reconfigure_entry
    result = await flow.async_step_reconfigure(user_input=None)
    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"


@pytest.mark.asyncio
async def test_async_step_reconfigure_updates_existing_entry(
    monkeypatch: pytest.MonkeyPatch, make_config_entry
) -> None:
    """Reconfigure should validate, enforce unique id, and request a reload."""
    flow = cf_mod.OPNsenseConfigFlow()
    flow.hass = MagicMock()

    async def _fake_validate_input(
        hass: HomeAssistant | None, user_input, config_step, errors, expected_id=None
    ) -> dict:
        return {}

    reconfigure_entry = make_config_entry(
        data={
            cf_mod.CONF_NAME: "Router",
            cf_mod.CONF_URL: "https://router.example",
            cf_mod.CONF_USERNAME: "old-user",
            cf_mod.CONF_PASSWORD: "old-pass",
            cf_mod.CONF_DEVICE_UNIQUE_ID: "router-id",
        }
    )
    monkeypatch.setattr(cf_mod, "validate_input", _fake_validate_input)
    flow._get_reconfigure_entry = lambda: reconfigure_entry
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_mismatch = MagicMock()
    flow.async_update_reload_and_abort = MagicMock(
        return_value={"type": "abort", "reason": "reconfigure_successful"}
    )

    result = await flow.async_step_reconfigure(
        {
            cf_mod.CONF_URL: "https://router.example",
            cf_mod.CONF_USERNAME: "new-user",
            cf_mod.CONF_PASSWORD: "new-pass",
            cf_mod.CONF_VERIFY_SSL: True,
        }
    )
    assert result["reason"] == "reconfigure_successful"
    flow.async_set_unique_id.assert_awaited_once_with("router-id")
    flow._abort_if_unique_id_mismatch.assert_called_once()
    flow.async_update_reload_and_abort.assert_called_once()


@pytest.mark.asyncio
async def test_async_step_import_abort_and_reauth_show_form(
    monkeypatch: pytest.MonkeyPatch, make_config_entry
) -> None:
    """Import failures should abort, and reauth should render and delegate correctly."""
    flow = cf_mod.OPNsenseConfigFlow()
    flow.hass = MagicMock()

    async def _import_errors(
        hass: HomeAssistant | None, user_input, config_step, errors, expected_id=None
    ) -> dict[str, str]:
        return {"base": "cannot_connect"}

    monkeypatch.setattr(cf_mod, "validate_input", _import_errors)
    result = await flow.async_step_import(
        {
            cf_mod.CONF_NAME: "Imported Router",
            cf_mod.CONF_URL: "https://router.example",
            cf_mod.CONF_USERNAME: "api-key",
            cf_mod.CONF_PASSWORD: "api-secret",
            cf_mod.CONF_DEVICE_UNIQUE_ID: "router-id",
        }
    )
    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"

    sentinel = {"type": "form", "step_id": "reauth_confirm"}
    flow.async_step_reauth_confirm = AsyncMock(return_value=sentinel)
    assert await flow.async_step_reauth({}) == sentinel

    reauth_entry = make_config_entry(
        data={
            cf_mod.CONF_NAME: "Router",
            cf_mod.CONF_URL: "https://router.example",
            cf_mod.CONF_USERNAME: "old-user",
            cf_mod.CONF_PASSWORD: "old-pass",
            cf_mod.CONF_DEVICE_UNIQUE_ID: "router-id",
        }
    )
    flow = cf_mod.OPNsenseConfigFlow()
    flow.hass = MagicMock()
    flow._get_reauth_entry = lambda: reauth_entry
    result = await flow.async_step_reauth_confirm()
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"


@pytest.mark.asyncio
async def test_device_tracker_shows_form_when_no_user_input(
    monkeypatch: pytest.MonkeyPatch, make_config_entry
) -> None:
    """async_step_device_tracker should show form containing data_schema when called without user_input."""
    cfg = make_config_entry(
        data={
            cf_mod.CONF_URL: "https://x",
            cf_mod.CONF_USERNAME: "u",
            cf_mod.CONF_PASSWORD: "p",
        },
        options={cf_mod.CONF_DEVICES: ["11:22:33:44:55:66"]},
    )

    flow = cf_mod.OPNsenseOptionsFlow(cfg)
    flow.hass = MagicMock()

    # monkeypatch _get_dt_entries to return an ordered dict-like mapping
    async def fake_get_dt_entries(
        hass: HomeAssistant | None, config, selected_devices
    ) -> dict[str, str]:
        return {"11:22:33:44:55:66": "label1", "aa:bb:cc:dd:ee:ff": "label2"}

    monkeypatch.setattr(cf_mod, "_get_dt_entries", fake_get_dt_entries)

    # ensure internals are present so we don't trigger config_entry property lookup
    flow._config = dict(cfg.data)
    flow._options = dict(cfg.options)
    # set a handler and make async_get_known_entry return our cfg so the flow can access
    # config_entry and options during unit tests without Home Assistant internals.
    flow.handler = "opnsense"
    flow.hass.config_entries.async_get_known_entry = MagicMock(return_value=cfg)

    res = await flow.async_step_device_tracker(user_input=None)
    assert res["type"] == "form"
    assert "data_schema" in res
    validated = res["data_schema"]({})
    assert cf_mod.CONF_DEVICES in validated


@pytest.mark.asyncio
async def test_device_tracker_handles_arp_lookup_failure(
    monkeypatch: pytest.MonkeyPatch, make_config_entry
) -> None:
    """ARP lookup failures should not abort the options flow form rendering."""
    cfg = make_config_entry(
        data={
            cf_mod.CONF_URL: "https://x",
            cf_mod.CONF_USERNAME: "u",
            cf_mod.CONF_PASSWORD: "p",
        },
        options={cf_mod.CONF_DEVICES: ["AA-BB-CC-DD-EE-FF"]},
    )
    flow = cf_mod.OPNsenseOptionsFlow(cfg)
    flow.hass = MagicMock()
    flow._config = dict(cfg.data)
    flow._options = dict(cfg.options)
    flow.handler = "opnsense"
    flow.hass.config_entries.async_get_known_entry = MagicMock(return_value=cfg)

    async def _raise(*args, **kwargs):
        raise aiohttp.ClientError("boom")

    monkeypatch.setattr(cf_mod, "_get_dt_entries", _raise)

    res = await flow.async_step_device_tracker(user_input=None)
    assert res["type"] == "form"
    assert res["errors"]["base"] == "cannot_connect"
    validated = res["data_schema"]({})
    assert validated[cf_mod.CONF_DEVICES] == ["aa:bb:cc:dd:ee:ff"]


@pytest.mark.asyncio
async def test_options_flow_device_tracker_user_input(
    monkeypatch: pytest.MonkeyPatch, make_config_entry
) -> None:
    """When user submits manual devices, they should be parsed and saved to options."""
    # Build a fake config_entry using shared factory
    config_entry = make_config_entry(
        data={
            cf_mod.CONF_URL: "https://x",
            cf_mod.CONF_USERNAME: "u",
            cf_mod.CONF_PASSWORD: "p",
        },
        options={cf_mod.CONF_DEVICE_TRACKER_ENABLED: True, cf_mod.CONF_DEVICES: []},
    )

    flow = cf_mod.OPNsenseOptionsFlow(config_entry)
    # attach hass with config_entries.update stub
    flow.hass = MagicMock()
    flow.hass.config_entries = MagicMock()
    flow.hass.config_entries.async_update_entry = MagicMock()
    # make the flow aware of its handler so config_entry property works during tests
    flow.handler = "opnsense"
    flow.hass.config_entries.async_get_known_entry = MagicMock(
        return_value=config_entry
    )

    # emulate what async_step_init would do: populate _config and _options from entry
    flow._config = dict(config_entry.data)
    flow._options = dict(config_entry.options)

    user_input = {
        cf_mod.CONF_MANUAL_DEVICES: "aa:bb:cc:dd:ee:ff\nbad\n11:22:33:44:55:66",
        cf_mod.CONF_DEVICES: ["11:22:33:44:55:66"],
    }

    result = await flow.async_step_device_tracker(user_input=user_input)

    # flow should have returned a create_entry
    assert result["type"] == "create_entry"

    # The flow should have parsed manual devices into _options
    assert cf_mod.CONF_DEVICES in flow._options
    assert "aa:bb:cc:dd:ee:ff" in flow._options[cf_mod.CONF_DEVICES]
    assert "11:22:33:44:55:66" in flow._options[cf_mod.CONF_DEVICES]
    assert flow._options[cf_mod.CONF_DEVICES] == [
        "11:22:33:44:55:66",
        "aa:bb:cc:dd:ee:ff",
    ]


@pytest.mark.asyncio
async def test_options_flow_device_tracker_track_all_clears_device_list(
    make_config_entry,
) -> None:
    """Track-all mode from init should persist the legacy empty-device-list behavior."""
    config_entry = make_config_entry(
        data={
            cf_mod.CONF_URL: "https://x",
            cf_mod.CONF_USERNAME: "u",
            cf_mod.CONF_PASSWORD: "p",
        },
        options={
            cf_mod.CONF_DEVICE_TRACKER_ENABLED: True,
            cf_mod.CONF_DEVICES: ["aa:bb:cc:dd:ee:ff"],
        },
    )

    flow = cf_mod.OPNsenseOptionsFlow(config_entry)
    flow.hass = MagicMock()
    flow.hass.config_entries = MagicMock()
    flow.hass.config_entries.async_update_entry = MagicMock()
    flow.handler = "opnsense"
    flow.hass.config_entries.async_get_known_entry = MagicMock(
        return_value=config_entry
    )
    flow._config = dict(config_entry.data)
    flow._options = dict(config_entry.options)

    result = await flow.async_step_init(
        user_input={
            cf_mod.CONF_DEVICE_TRACKING_MODE: cf_mod.DEVICE_TRACKING_MODE_ALL,
            cf_mod.CONF_GRANULAR_SYNC_OPTIONS: False,
        }
    )

    assert result["type"] == "create_entry"
    assert flow._options[cf_mod.CONF_DEVICES] == []


@pytest.mark.asyncio
async def test_options_flow_init_selected_mode_shows_picker_step(
    monkeypatch: pytest.MonkeyPatch, make_config_entry
) -> None:
    """Selected-only mode should continue to the device picker step."""
    config_entry = make_config_entry(
        data={
            cf_mod.CONF_URL: "https://x",
            cf_mod.CONF_USERNAME: "u",
            cf_mod.CONF_PASSWORD: "p",
        },
        options={cf_mod.CONF_DEVICE_TRACKER_ENABLED: False, cf_mod.CONF_DEVICES: []},
    )
    flow = cf_mod.OPNsenseOptionsFlow(config_entry)
    flow.hass = MagicMock()
    flow.hass.config_entries = MagicMock()
    flow.hass.config_entries.async_update_entry = MagicMock()
    flow.handler = "opnsense"
    flow.hass.config_entries.async_get_known_entry = MagicMock(
        return_value=config_entry
    )
    monkeypatch.setattr(cf_mod, "_get_dt_entries", AsyncMock(return_value={}))

    result = await flow.async_step_init(
        user_input={
            cf_mod.CONF_DEVICE_TRACKING_MODE: cf_mod.DEVICE_TRACKING_MODE_SELECTED,
            cf_mod.CONF_GRANULAR_SYNC_OPTIONS: False,
        }
    )
    assert result["type"] == "form"
    assert result["step_id"] == "device_tracker"


@pytest.mark.asyncio
async def test_options_flow_init_and_device_tracker_guard_branches(
    make_config_entry,
) -> None:
    """Options flow should render init form and clear device selections when disabled."""
    config_entry = make_config_entry(
        data={
            cf_mod.CONF_URL: "https://x",
            cf_mod.CONF_USERNAME: "u",
            cf_mod.CONF_PASSWORD: "p",
            cf_mod.TRACKED_MACS: ["aa:bb:cc:dd:ee:ff"],
        },
        options={
            cf_mod.CONF_DEVICE_TRACKER_ENABLED: False,
            cf_mod.CONF_DEVICES: ["aa:bb:cc:dd:ee:ff"],
        },
    )

    flow = cf_mod.OPNsenseOptionsFlow(config_entry)
    flow.hass = MagicMock()
    flow.hass.config_entries = MagicMock()
    flow.hass.config_entries.async_update_entry = MagicMock()
    flow.handler = "opnsense"
    flow.hass.config_entries.async_get_known_entry = MagicMock(
        return_value=config_entry
    )
    flow._config = dict(config_entry.data)
    flow._options = dict(config_entry.options)

    result = await flow.async_step_init(user_input=None)
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await flow.async_step_device_tracker(
        user_input={cf_mod.CONF_MANUAL_DEVICES: "", cf_mod.CONF_DEVICES: []}
    )
    assert result["type"] == "create_entry"
    assert cf_mod.CONF_DEVICES not in flow._options
    assert cf_mod.TRACKED_MACS not in flow._config
