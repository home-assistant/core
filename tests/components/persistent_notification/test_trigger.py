"""The tests for the persistent notification component triggers."""

from typing import Any

from homeassistant.components import persistent_notification as pn
from homeassistant.components.persistent_notification import trigger
from homeassistant.core import Context, HomeAssistant, callback


async def test_automation_with_pn_trigger(hass: HomeAssistant) -> None:
    """Test automation with a persistent_notification trigger."""

    result_any = []
    result_dismissed = []
    result_id = []

    trigger_info = {"trigger_data": {}}

    @callback
    def trigger_callback_any(
        run_variables: dict[str, Any], context: Context | None = None
    ) -> None:
        result_any.append(run_variables)

    await trigger.async_attach_trigger(
        hass,
        {"platform": "persistent_notification"},
        trigger_callback_any,
        trigger_info,
    )

    @callback
    def trigger_callback_dismissed(
        run_variables: dict[str, Any], context: Context | None = None
    ) -> None:
        result_dismissed.append(run_variables)

    await trigger.async_attach_trigger(
        hass,
        {"platform": "persistent_notification", "update_type": "removed"},
        trigger_callback_dismissed,
        trigger_info,
    )

    @callback
    def trigger_callback_id(
        run_variables: dict[str, Any], context: Context | None = None
    ) -> None:
        result_id.append(run_variables)

    await trigger.async_attach_trigger(
        hass,
        {"platform": "persistent_notification", "notification_id": "42"},
        trigger_callback_id,
        trigger_info,
    )

    await hass.services.async_call(
        pn.DOMAIN,
        "create",
        {"notification_id": "test_notification", "message": "test"},
        blocking=True,
    )

    result = result_any[0].get("trigger")
    assert result["platform"] == "persistent_notification"
    assert result["update_type"] == pn.UpdateType.ADDED
    assert result["notification"]["notification_id"] == "test_notification"
    assert result["notification"]["message"] == "test"

    assert len(result_dismissed) == 0
    assert len(result_id) == 0

    await hass.services.async_call(
        pn.DOMAIN,
        "dismiss",
        {"notification_id": "test_notification"},
        blocking=True,
    )

    result = result_any[1].get("trigger")
    assert result["platform"] == "persistent_notification"
    assert result["update_type"] == pn.UpdateType.REMOVED
    assert result["notification"]["notification_id"] == "test_notification"
    assert result["notification"]["message"] == "test"
    assert result_any[1] == result_dismissed[0]

    assert len(result_id) == 0

    await hass.services.async_call(
        pn.DOMAIN,
        "create",
        {"notification_id": "42", "message": "Forty Two"},
        blocking=True,
    )

    result = result_any[2].get("trigger")
    assert result["platform"] == "persistent_notification"
    assert result["update_type"] == pn.UpdateType.ADDED
    assert result["notification"]["notification_id"] == "42"
    assert result["notification"]["message"] == "Forty Two"
    assert result_any[2] == result_id[0]
