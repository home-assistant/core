from unittest.mock import patch

from homeassistant.components.connectsense.const import (
    CONF_AR_ANY_FAIL,
    CONF_AR_DELAY_MIN,
    CONF_AR_MAX_REBOOTS,
    CONF_AR_OFF_SECONDS,
    CONF_AR_PING_FAIL,
    CONF_AR_POWER_FAIL,
    CONF_AR_TARGET_1,
    CONF_AR_TARGET_2,
    CONF_AR_TARGET_3,
    CONF_AR_TARGET_4,
    CONF_AR_TARGET_5,
    CONF_AR_TRIGGER_MIN,
    CONF_NOTIFY_CODE_OFF,
    CONF_NOTIFY_CODE_ON,
    CONF_NOTIFY_CODE_REBOOT,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_SERVICE,
)


async def test_options_flow_updates_options(hass, setup_entry):
    entry = setup_entry

    with patch(
        "homeassistant.components.connectsense.options_flow.RebooterOptionsFlowHandler._fetch_device_config",
        return_value=None,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == "form"
        assert result["step_id"] == "init"

        user_input = {
            CONF_AR_OFF_SECONDS: "30",
            CONF_AR_POWER_FAIL: True,
            CONF_AR_PING_FAIL: False,
            CONF_AR_TRIGGER_MIN: 5,
            CONF_AR_DELAY_MIN: 1,
            CONF_AR_MAX_REBOOTS: "2",
            CONF_AR_ANY_FAIL: "any",
            CONF_AR_TARGET_1: "https://foo.com",
            CONF_AR_TARGET_2: "bar.com",
            CONF_AR_TARGET_3: "",
            CONF_AR_TARGET_4: "",
            CONF_AR_TARGET_5: "",
            CONF_NOTIFY_ENABLED: True,
            CONF_NOTIFY_SERVICE: "notify.test",
            CONF_NOTIFY_CODE_OFF: False,
            CONF_NOTIFY_CODE_ON: False,
            CONF_NOTIFY_CODE_REBOOT: False,
        }

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=user_input
        )

    assert result["type"] == "create_entry"
    data = result["data"]

    assert data[CONF_AR_OFF_SECONDS] == 30  # coerced to int and clamped
    assert data[CONF_AR_ANY_FAIL] is True
    assert data[CONF_AR_MAX_REBOOTS] == 2
    assert data[CONF_AR_TARGET_1] == "foo.com"  # scheme stripped
    assert data[CONF_AR_TARGET_2] == "bar.com"
    assert data[CONF_NOTIFY_ENABLED] is True
    assert data[CONF_NOTIFY_SERVICE] == "notify.test"
    assert data[CONF_NOTIFY_CODE_OFF] is False
    assert data[CONF_NOTIFY_CODE_ON] is False
    assert data[CONF_NOTIFY_CODE_REBOOT] is False
