"""The tests for local file sensor platform."""
from unittest.mock import Mock, mock_open, patch

from homeassistant.components.fail2ban.sensor import (
    STATE_ALL_BANS,
    STATE_CURRENT_BANS,
    BanLogParser,
    BanSensor,
)
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component


def fake_log(log_key):
    """Return a fake fail2ban log."""
    fake_log_dict = {
        "single_ban": (
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Ban 111.111.111.111"
        ),
        "ipv6_ban": (
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Ban 2607:f0d0:1002:51::4"
        ),
        "multi_ban": (
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Ban 111.111.111.111\n"
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Ban 222.222.222.222"
        ),
        "multi_jail": (
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Ban 111.111.111.111\n"
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_two] Ban 222.222.222.222"
        ),
        "unban_all": (
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Ban 111.111.111.111\n"
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Unban 111.111.111.111\n"
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Ban 222.222.222.222\n"
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Unban 222.222.222.222"
        ),
        "unban_one": (
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Ban 111.111.111.111\n"
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Ban 222.222.222.222\n"
            "2017-01-01 12:23:35 fail2ban.actions [111]: "
            "NOTICE [jail_one] Unban 111.111.111.111"
        ),
    }
    return fake_log_dict[log_key]


@patch("os.path.isfile", Mock(return_value=True))
async def test_setup(hass):
    """Test that sensor can be setup."""
    config = {"sensor": {"platform": "fail2ban", "jails": ["jail_one"]}}
    mock_fh = mock_open()
    with patch("homeassistant.components.fail2ban.sensor.open", mock_fh, create=True):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()
    assert_setup_component(1, "sensor")


@patch("os.path.isfile", Mock(return_value=True))
async def test_multi_jails(hass):
    """Test that multiple jails can be set up as sensors.."""
    config = {"sensor": {"platform": "fail2ban", "jails": ["jail_one", "jail_two"]}}
    mock_fh = mock_open()
    with patch("homeassistant.components.fail2ban.sensor.open", mock_fh, create=True):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()
    assert_setup_component(2, "sensor")


async def test_single_ban(hass):
    """Test that log is parsed correctly for single ban."""
    log_parser = BanLogParser("/test/fail2ban.log")
    sensor = BanSensor("fail2ban", "jail_one", log_parser)
    assert sensor.name == "fail2ban jail_one"
    mock_fh = mock_open(read_data=fake_log("single_ban"))
    with patch("homeassistant.components.fail2ban.sensor.open", mock_fh, create=True):
        sensor.update()

    assert sensor.state == "111.111.111.111"
    assert sensor.extra_state_attributes[STATE_CURRENT_BANS] == ["111.111.111.111"]
    assert sensor.extra_state_attributes[STATE_ALL_BANS] == ["111.111.111.111"]


async def test_ipv6_ban(hass):
    """Test that log is parsed correctly for IPV6 bans."""
    log_parser = BanLogParser("/test/fail2ban.log")
    sensor = BanSensor("fail2ban", "jail_one", log_parser)
    assert sensor.name == "fail2ban jail_one"
    mock_fh = mock_open(read_data=fake_log("ipv6_ban"))
    with patch("homeassistant.components.fail2ban.sensor.open", mock_fh, create=True):
        sensor.update()

    assert sensor.state == "2607:f0d0:1002:51::4"
    assert sensor.extra_state_attributes[STATE_CURRENT_BANS] == ["2607:f0d0:1002:51::4"]
    assert sensor.extra_state_attributes[STATE_ALL_BANS] == ["2607:f0d0:1002:51::4"]


async def test_multiple_ban(hass):
    """Test that log is parsed correctly for multiple ban."""
    log_parser = BanLogParser("/test/fail2ban.log")
    sensor = BanSensor("fail2ban", "jail_one", log_parser)
    assert sensor.name == "fail2ban jail_one"
    mock_fh = mock_open(read_data=fake_log("multi_ban"))
    with patch("homeassistant.components.fail2ban.sensor.open", mock_fh, create=True):
        sensor.update()

    assert sensor.state == "222.222.222.222"
    assert sensor.extra_state_attributes[STATE_CURRENT_BANS] == [
        "111.111.111.111",
        "222.222.222.222",
    ]
    assert sensor.extra_state_attributes[STATE_ALL_BANS] == [
        "111.111.111.111",
        "222.222.222.222",
    ]


async def test_unban_all(hass):
    """Test that log is parsed correctly when unbanning."""
    log_parser = BanLogParser("/test/fail2ban.log")
    sensor = BanSensor("fail2ban", "jail_one", log_parser)
    assert sensor.name == "fail2ban jail_one"
    mock_fh = mock_open(read_data=fake_log("unban_all"))
    with patch("homeassistant.components.fail2ban.sensor.open", mock_fh, create=True):
        sensor.update()

    assert sensor.state == "None"
    assert sensor.extra_state_attributes[STATE_CURRENT_BANS] == []
    assert sensor.extra_state_attributes[STATE_ALL_BANS] == [
        "111.111.111.111",
        "222.222.222.222",
    ]


async def test_unban_one(hass):
    """Test that log is parsed correctly when unbanning one ip."""
    log_parser = BanLogParser("/test/fail2ban.log")
    sensor = BanSensor("fail2ban", "jail_one", log_parser)
    assert sensor.name == "fail2ban jail_one"
    mock_fh = mock_open(read_data=fake_log("unban_one"))
    with patch("homeassistant.components.fail2ban.sensor.open", mock_fh, create=True):
        sensor.update()

    assert sensor.state == "222.222.222.222"
    assert sensor.extra_state_attributes[STATE_CURRENT_BANS] == ["222.222.222.222"]
    assert sensor.extra_state_attributes[STATE_ALL_BANS] == [
        "111.111.111.111",
        "222.222.222.222",
    ]


async def test_multi_jail(hass):
    """Test that log is parsed correctly when using multiple jails."""
    log_parser = BanLogParser("/test/fail2ban.log")
    sensor1 = BanSensor("fail2ban", "jail_one", log_parser)
    sensor2 = BanSensor("fail2ban", "jail_two", log_parser)
    assert sensor1.name == "fail2ban jail_one"
    assert sensor2.name == "fail2ban jail_two"
    mock_fh = mock_open(read_data=fake_log("multi_jail"))
    with patch("homeassistant.components.fail2ban.sensor.open", mock_fh, create=True):
        sensor1.update()
        sensor2.update()

    assert sensor1.state == "111.111.111.111"
    assert sensor1.extra_state_attributes[STATE_CURRENT_BANS] == ["111.111.111.111"]
    assert sensor1.extra_state_attributes[STATE_ALL_BANS] == ["111.111.111.111"]
    assert sensor2.state == "222.222.222.222"
    assert sensor2.extra_state_attributes[STATE_CURRENT_BANS] == ["222.222.222.222"]
    assert sensor2.extra_state_attributes[STATE_ALL_BANS] == ["222.222.222.222"]


async def test_ban_active_after_update(hass):
    """Test that ban persists after subsequent update."""
    log_parser = BanLogParser("/test/fail2ban.log")
    sensor = BanSensor("fail2ban", "jail_one", log_parser)
    assert sensor.name == "fail2ban jail_one"
    mock_fh = mock_open(read_data=fake_log("single_ban"))
    with patch("homeassistant.components.fail2ban.sensor.open", mock_fh, create=True):
        sensor.update()
        assert sensor.state == "111.111.111.111"
        sensor.update()
        assert sensor.state == "111.111.111.111"
    assert sensor.extra_state_attributes[STATE_CURRENT_BANS] == ["111.111.111.111"]
    assert sensor.extra_state_attributes[STATE_ALL_BANS] == ["111.111.111.111"]
