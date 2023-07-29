"""Test schlage lock."""

from datetime import datetime, timedelta
from unittest.mock import Mock, create_autospec

from pyschlage.code import AccessCode
from pyschlage.exceptions import UnknownError
from pyschlage.log import LockLog

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed


async def test_lock_device_registry(
    hass: HomeAssistant, mock_added_config_entry: ConfigEntry
) -> None:
    """Test lock is added to device registry."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={("schlage", "test")})
    assert device.model == "<model-name>"
    assert device.sw_version == "1.0"
    assert device.name == "Vault Door"
    assert device.manufacturer == "Schlage"


async def test_lock_services(
    hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
) -> None:
    """Test lock services."""
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        service_data={ATTR_ENTITY_ID: "lock.vault_door"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.lock.assert_called_once_with()

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        service_data={ATTR_ENTITY_ID: "lock.vault_door"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.unlock.assert_called_once_with()

    await hass.config_entries.async_unload(mock_added_config_entry.entry_id)


class TestChangedBy:
    """Test parsing of logs for the changed_by attribute."""

    async def test_thumbturn_unlock(
        self, hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
    ) -> None:
        """Test parsing a thumbturn unlock message."""
        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Locked by keypad",
            ),
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 1, 0, 0),
                message="Unlocked by thumbturn",
            ),
        ]

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "thumbturn"

    async def test_thumbturn_lock(
        self, hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
    ) -> None:
        """Test parsing a thumbturn lock message."""
        mock_lock.is_locked = True
        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Unlocked by keypad",
            ),
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 1, 0, 0),
                message="Locked by thumbturn",
            ),
        ]

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "thumbturn"

    async def test_keypad_unlock(
        self, hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
    ) -> None:
        """Test parsing a keypad unlock message."""
        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Locked by keypad",
            ),
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 1, 0, 0),
                message="Unlocked by keypad",
                access_code_id="__access-code-id__",
            ),
        ]
        mock_access_code = create_autospec(AccessCode)
        mock_access_code.configure_mock(
            name="SECRET CODE",
            access_code_id="__access-code-id__",
        )
        mock_lock.access_codes.return_value = [mock_access_code]

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "keypad - SECRET CODE"

    async def test_keypad_unknown_access_code_unlock(
        self, hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
    ) -> None:
        """Test parsing a keypad unlock message with an unknown access code."""
        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Locked by keypad",
            ),
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 1, 0, 0),
                message="Unlocked by keypad",
                access_code_id="__access-code-id__",
            ),
        ]

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "keypad"

    async def test_keypad_access_codes_not_loaded(
        self, hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
    ) -> None:
        """Test parsing a keypad unlock message when access codes fail to load."""
        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Locked by keypad",
            ),
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 1, 0, 0),
                message="Unlocked by keypad",
                access_code_id="__access-code-id__",
            ),
        ]
        mock_lock.access_codes.side_effect = UnknownError("Access codes not loaded")

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "keypad"

    async def test_keypad_use_previous_access_codes(
        self,
        hass: HomeAssistant,
        mock_lock: Mock,
        mock_added_config_entry: ConfigEntry,
    ) -> None:
        """Test that parsing keypad unlock falls back to previously loaded access codes."""
        mock_lock.logs.return_value = []
        mock_access_code = create_autospec(AccessCode)
        mock_access_code.configure_mock(
            name="SECRET CODE",
            access_code_id="__access-code-id__",
        )
        mock_lock.access_codes.return_value = [mock_access_code]

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Locked by keypad",
            ),
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 1, 0, 0),
                message="Unlocked by keypad",
                access_code_id="__access-code-id__",
            ),
        ]
        mock_lock.access_codes.side_effect = UnknownError("Access codes not loaded")

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "keypad - SECRET CODE"

    async def test_keypad_use_previous_logs(
        self,
        hass: HomeAssistant,
        mock_lock: Mock,
        mock_added_config_entry: ConfigEntry,
    ) -> None:
        """Test parsing keypad unlock message will fall back to previously loaded logs."""
        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Locked by keypad",
            ),
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 1, 0, 0),
                message="Unlocked by keypad",
                access_code_id="__access-code-id__",
            ),
        ]
        mock_access_code = create_autospec(AccessCode)
        mock_access_code.configure_mock(
            name="SECRET CODE",
            access_code_id="__access-code-id__",
        )
        mock_lock.access_codes.return_value = [mock_access_code]

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "keypad - SECRET CODE"

        # Change the name of the access code, which should get reflected when we
        # re-compute changed_by.
        mock_access_code.name = "LESS SECRET CODE"
        mock_lock.logs.side_effect = UnknownError("Logs not loaded")

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "keypad - LESS SECRET CODE"

    async def test_mobile_device_unlock(
        self,
        hass: HomeAssistant,
        mock_schlage: Mock,
        mock_lock: Mock,
        mock_user: Mock,
        mock_added_config_entry: ConfigEntry,
    ) -> None:
        """Test parsing a mobile device unlock message."""
        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Locked by keypad",
            ),
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 1, 0, 0),
                message="Unlocked by mobile device",
                accessor_id="__user-id__",
            ),
        ]
        mock_schlage.users.return_value = [mock_user]

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "mobile device - robot"

    async def test_mobile_device_users_not_loaded(
        self,
        hass: HomeAssistant,
        mock_schlage: Mock,
        mock_lock: Mock,
        mock_added_config_entry: ConfigEntry,
    ) -> None:
        """Test parsing a mobile device unlock message without users loaded."""
        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Locked by keypad",
            ),
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 1, 0, 0),
                message="Unlocked by mobile device",
                accessor_id="__user-id__",
            ),
        ]
        mock_schlage.users.side_effect = UnknownError("Could not load users")

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "mobile device"

    async def test_mobile_device_use_previous_users(
        self,
        hass: HomeAssistant,
        mock_schlage: Mock,
        mock_lock: Mock,
        mock_user: Mock,
        mock_added_config_entry: ConfigEntry,
    ) -> None:
        """Test parsing a mobile device unlock message falls back on previously loaded users."""
        mock_lock.logs.return_value = []
        mock_schlage.users.return_value = [mock_user]

        # Make the coordinator refresh data to load the user.
        first_refresh = utcnow() + timedelta(seconds=31)
        async_fire_time_changed(hass, first_refresh)
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        # No logs, no changed_by.
        assert lock_device.attributes.get("changed_by") is None

        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Locked by keypad",
            ),
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 1, 0, 0),
                message="Unlocked by mobile device",
                accessor_id="__user-id__",
            ),
        ]
        mock_schlage.users.side_effect = UnknownError("Failed to load users")

        # Make the coordinator refresh data again.
        async_fire_time_changed(hass, first_refresh + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "mobile device - robot"

    async def test_no_useful_logs(
        self, hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
    ) -> None:
        """Test having no relevant log entries."""
        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Some other log message",
            ),
        ]

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") is None

    async def test_old_state_is_retained_with_unknown_log(
        self, hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
    ) -> None:
        """Test that old changed_by value is unchanged with new irrelevant logs."""
        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 0, 0, 0),
                message="Locked by keypad",
            ),
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 1, 0, 0),
                message="Unlocked by keypad",
                access_code_id="__access-code-id__",
            ),
        ]

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "keypad"

        mock_lock.logs.return_value = [
            create_autospec(
                LockLog,
                created_at=datetime(2023, 1, 1, 2, 0, 0),
                message="Some other log message",
            )
        ]
        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        # Make sure changed_by didn't get reset.
        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") == "keypad"

    async def test_cannot_load_logs(
        self, hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
    ) -> None:
        """Test that a failure to load logs is not terminal."""
        mock_lock.logs.side_effect = UnknownError("Cannot load logs")

        # Make the coordinator refresh data.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

        lock_device = hass.states.get("lock.vault_door")
        assert lock_device is not None
        assert lock_device.attributes.get("changed_by") is None
