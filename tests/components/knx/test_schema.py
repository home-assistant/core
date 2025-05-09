"""Tests for the schema validators of the KNX integration."""

from typing import Any

import pytest
import voluptuous as vol
from xknx.dpt import DPTVoltage

from homeassistant.components.knx.schema import (
    GroupAddressConfigSchema,
    GroupAddressListSchema,
    GroupAddressSchema,
    SyncStateSchema,
)
from homeassistant.components.knx.storage.const import (
    CONF_DPT,
    CONF_GA_PASSIVE,
    CONF_GA_STATE,
    CONF_GA_WRITE,
)
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit


class TestGroupAddressSchema:
    """Test class for GroupAddressSchema validation and serialization."""

    # Test cases for the __call__ method.
    # (1) test_name: descriptive name for the test
    # (2) input_value: the value to validate
    # (3) allow_internal_address: whether internal addresses are allowed
    # (4) expected: the expected result (either valid value or vol.Invalid)
    GROUP_ADDRESS_SCHEMA_CALL_CASES: tuple[tuple[str, Any, bool, Any], ...] = (
        ("valid_string_address", "1/2/3", False, "1/2/3"),
        ("valid_int_address", 123, False, 123),
        ("invalid_none", None, False, vol.Invalid),
        ("invalid_list_type", [1, 2], False, vol.Invalid),
        ("valid_internal_address", "i1/2/3", True, "i1/2/3"),
        ("invalid_internal_not_allowed", "i1/2/3", False, vol.Invalid),
        ("invalid_random_string", "abc", True, vol.Invalid),
    )

    # Test cases for the serialize method.
    # (1) test_name: descriptive name for the test
    # (2) init_options: constructor kwargs for GroupAddressSchema
    # (3) expected_allow_internal: expected boolean in the serialized dict
    GROUP_ADDRESS_SCHEMA_SERIALIZE_CASES: tuple[
        tuple[str, dict[str, bool], bool], ...
    ] = (
        ("defaults", {}, True),
        ("disallow_internal_address", {"allow_internal_address": False}, False),
        ("allow_internal_address_true", {"allow_internal_address": True}, True),
    )

    @pytest.mark.parametrize(
        ("test_name", "input_value", "allow_internal", "expected"),
        GROUP_ADDRESS_SCHEMA_CALL_CASES,
        ids=[case[0] for case in GROUP_ADDRESS_SCHEMA_CALL_CASES],
    )
    def test_group_address_schema_call(
        self,
        hass: HomeAssistant,
        knx: KNXTestKit,
        test_name: str,
        input_value: Any,
        allow_internal: bool,
        expected: Any,
    ) -> None:
        """Test the __call__ method of GroupAddressSchema.

        - If 'expected' is vol.Invalid, we expect a vol.Invalid exception.
        - Otherwise, we verify that the returned value matches 'expected'.
        """
        validator = GroupAddressSchema(allow_internal_address=allow_internal)

        if expected == vol.Invalid:
            with pytest.raises(vol.Invalid):
                validator(input_value)
        else:
            result = validator(input_value)
            assert result == expected, (
                f"Test case '{test_name}' failed: Expected '{expected}', got '{result}'."
            )

    @pytest.mark.parametrize(
        ("test_name", "init_options", "expected_allow_internal"),
        GROUP_ADDRESS_SCHEMA_SERIALIZE_CASES,
        ids=[case[0] for case in GROUP_ADDRESS_SCHEMA_SERIALIZE_CASES],
    )
    def test_group_address_schema_serialize(
        self,
        test_name: str,
        init_options: dict[str, bool],
        expected_allow_internal: bool,
    ) -> None:
        """Test the serialization method of GroupAddressSchema.

        Ensures that the returned dictionary has the correct 'type' value and
        includes 'allow_internal_address' from the instance options.
        """

        def mock_convert(schema: Any) -> Any:
            return "converted_schema"

        instance = GroupAddressSchema(**init_options)
        result = GroupAddressSchema.serialize(instance, mock_convert)

        assert isinstance(result, dict), "Serialization result must be a dictionary."
        assert result["type"] == "group_address", (
            f"Test case '{test_name}' failed: 'type' is not 'group_address'."
        )
        assert result["allow_internal_address"] == expected_allow_internal, (
            f"Test case '{test_name}' failed: 'allow_internal_address' mismatch."
        )


class TestGroupAddressListSchema:
    """Test class for GroupAddressListSchema validation and serialization."""

    # Test data for the __call__ method:
    # (1) test_name: descriptive name for the test
    # (2) input_value: the data to validate
    # (3) allow_internal_addresses: whether internal addresses are allowed
    # (4) expected: the expected result – either a list, an empty list, or vol.Invalid
    GROUP_ADDRESS_LIST_CALL_CASES: tuple[tuple[str, Any, bool, Any], ...] = (
        # A list of standard group addresses (strings) without internal addresses
        (
            "valid_list_string_ga_no_internal",
            ["1/2/3", "2/3/4"],
            False,
            ["1/2/3", "2/3/4"],
        ),
        # A list of int addresses without internal addresses
        ("valid_list_int_ga_no_internal", [123, 456], False, [123, 456]),
        # An empty list is valid
        ("valid_empty_list_no_internal", [], False, []),
        # None -> coerce to empty list
        ("valid_none_coerced_to_empty_list_no_internal", None, False, []),
        # False -> coerce to empty list
        ("valid_boolean_false_coerced_to_empty_list_no_internal", False, False, []),
        # True -> invalid
        ("invalid_boolean_true_no_internal", True, False, vol.Invalid),
        # Invalid single string instead of a list
        ("invalid_single_string_no_internal", "1/2/3", False, vol.Invalid),
        # Mixed list with a None value
        ("invalid_mixed_list_no_internal", [123, None], False, vol.Invalid),
        # Cases specifically for allow_internal_addresses=True
        (
            "valid_list_of_internal_addresses",
            ["i1/2/3", "i2/3/4"],
            True,
            ["i1/2/3", "i2/3/4"],
        ),
        # Mixed with an internal address not allowed
        (
            "invalid_internal_not_allowed_in_list",
            ["1/2/3", "i3/4/5"],
            False,
            vol.Invalid,
        ),
        # Invalid single internal address when a list is not given
        ("invalid_single_internal_as_non_list", "i1/2/3", True, vol.Invalid),
    )

    # Test data for the serialize method:
    # (1) test_name: descriptive name
    # (2) init_options: dict to pass to the constructor
    # (3) expected_allow_internal: the expected boolean in the underlying schema
    GROUP_ADDRESS_LIST_SERIALIZE_CASES: tuple[
        tuple[str, dict[str, bool], bool], ...
    ] = (
        # Default is allow_internal_addresses=True
        ("defaults", {}, True),
        ("disallow_internal", {"allow_internal_addresses": False}, False),
        ("allow_internal_true", {"allow_internal_addresses": True}, True),
    )

    @pytest.mark.parametrize(
        ("test_name", "input_value", "allow_internal", "expected"),
        GROUP_ADDRESS_LIST_CALL_CASES,
        ids=[case[0] for case in GROUP_ADDRESS_LIST_CALL_CASES],
    )
    def test_group_address_list_call(
        self,
        hass: HomeAssistant,
        knx: KNXTestKit,
        test_name: str,
        input_value: Any,
        allow_internal: bool,
        expected: Any,
    ) -> None:
        """Test the __call__ method of GroupAddressListSchema.

        - If 'expected' is vol.Invalid, we expect a vol.Invalid exception.
        - Otherwise, we verify that the returned list matches 'expected'.
        """
        validator = GroupAddressListSchema(allow_internal_addresses=allow_internal)

        if expected == vol.Invalid:
            with pytest.raises(vol.Invalid):
                validator(input_value)
        else:
            result = validator(input_value)
            assert result == expected, (
                f"Test case '{test_name}' failed: Expected {expected}, got {result}."
            )

    @pytest.mark.parametrize(
        ("test_name", "init_options", "expected_allow_internal"),
        GROUP_ADDRESS_LIST_SERIALIZE_CASES,
        ids=[case[0] for case in GROUP_ADDRESS_LIST_SERIALIZE_CASES],
    )
    def test_group_address_list_serialize(
        self,
        test_name: str,
        init_options: dict[str, bool],
        expected_allow_internal: bool,
    ) -> None:
        """Test the serialize method of GroupAddressListSchema.

        Ensures that the returned dictionary has the correct structure.
        'items' is the serialization of a GroupAddressSchema with the same allow_internal_addresses
        flag. We only see 'converted_schema' from the mock here, but we confirm it was used.
        """

        def mock_convert(_: Any) -> Any:
            return "converted_schema"

        instance = GroupAddressListSchema(**init_options)
        result = GroupAddressListSchema.serialize(instance, mock_convert)

        assert isinstance(result, dict), "Serialization result must be a dictionary."
        assert result["type"] == "group_address_list", (
            f"Test case '{test_name}' failed: 'type' is not 'group_address_list'."
        )
        assert result["items"] == "converted_schema", (
            f"Test case '{test_name}' failed: 'items' was not 'converted_schema'."
        )

        # Optionally, verify that the instance has the correct allow_internal_addresses
        assert instance.allow_internal_addresses == expected_allow_internal, (
            f"Test case '{test_name}' failed: allow_internal_addresses mismatch."
        )


class TestSyncStateSchema:
    """Test class for SyncStateSchema validation and serialization."""

    # Test data for the __call__ method:
    # (1) test_name: descriptive name for the test
    # (2) input_value: the value to validate
    # (3) expected: either a valid output (if valid) or vol.Invalid (if invalid)
    SYNC_STATE_SCHEMA_CALL_CASES: tuple[tuple[str, Any, Any], ...] = (
        # Valid integers in range
        ("valid_int_min", 2, 2),
        ("valid_int_max", 1440, 1440),
        # Invalid integers
        ("invalid_int_below_min", 1, vol.Invalid),
        ("invalid_int_above_max", 1441, vol.Invalid),
        # Valid booleans
        ("valid_bool_true", True, True),
        ("valid_bool_false", False, False),
        # Valid strings matching the pattern
        ("valid_string_init", "init", "init"),
        ("valid_string_expire", "expire", "expire"),
        ("valid_string_every", "every", "every"),
        ("valid_string_every_number", "every 42", "every 42"),
        # Invalid strings (typo or extra non-digit info)
        ("invalid_string_typo", "expyre", vol.Invalid),
        ("invalid_string_pattern", "init abc", vol.Invalid),
    )

    # Test data for the serialize method:
    # (1) test_name: descriptive name for the test
    SYNC_STATE_SCHEMA_SERIALIZE_CASES: tuple[tuple[str], ...] = (
        ("serialize_default",),
    )

    @pytest.mark.parametrize(
        ("test_name", "input_value", "expected"),
        SYNC_STATE_SCHEMA_CALL_CASES,
        ids=[case[0] for case in SYNC_STATE_SCHEMA_CALL_CASES],
    )
    def test_sync_state_schema_call(
        self,
        hass: HomeAssistant,
        knx: KNXTestKit,
        test_name: str,
        input_value: Any,
        expected: Any,
    ) -> None:
        """Test the __call__ method of SyncStateSchema.

        - If 'expected' is vol.Invalid, we expect a vol.Invalid exception.
        - Otherwise, we check that the return value matches 'expected'.
        """
        validator = SyncStateSchema()

        if expected == vol.Invalid:
            with pytest.raises(vol.Invalid):
                validator(input_value)
        else:
            result = validator(input_value)
            assert result == expected, (
                f"Test case '{test_name}' failed: "
                f"Expected '{expected}', got '{result}'."
            )

    @pytest.mark.parametrize(
        "test_name",
        SYNC_STATE_SCHEMA_SERIALIZE_CASES,
        ids=[case[0] for case in SYNC_STATE_SCHEMA_SERIALIZE_CASES],
    )
    def test_sync_state_schema_serialize(self, test_name: str) -> None:
        """Test the serialization method of SyncStateSchema.

        Ensures that the returned dictionary has the correct 'type' value.
        """

        def mock_convert(schema: Any) -> Any:
            return "converted_schema"

        instance = SyncStateSchema()
        result = SyncStateSchema.serialize(instance, mock_convert)

        assert isinstance(result, dict), "Serialization result must be a dictionary."
        assert result["type"] == "sync_state", (
            f"Test case '{test_name}' failed: 'type' is not 'sync_state'."
        )


class TestGroupAddressConfigSchema:
    """Test class for GroupAddressConfigSchema."""

    # Test cases for constructor validation (the __post_init__ checks).
    # (1) test_name: descriptive name
    # (2) constructor_kwargs: dictionary of arguments to pass into GroupAddressConfigSchema
    # (3) expect_error: True if we expect a ValueError, otherwise False
    CONFIG_CONSTRUCTOR_CASES: tuple[tuple[str, dict[str, Any], bool], ...] = (
        (
            "valid_minimal",
            {"allowed_dpts": (DPTVoltage,)},
            False,
        ),
        (
            "no_dpts_provided",
            {"allowed_dpts": ()},
            True,
        ),
        (
            "both_write_and_state_disabled",
            {"allowed_dpts": (DPTVoltage,), "write": False, "state": False},
            True,
        ),
        (
            "write_disabled_but_required",
            {"allowed_dpts": (DPTVoltage,), "write": False, "write_required": True},
            True,
        ),
        (
            "state_disabled_but_required",
            {"allowed_dpts": (DPTVoltage,), "state": False, "state_required": True},
            True,
        ),
        (
            "state_disabled_but_passive",
            {"allowed_dpts": (DPTVoltage,), "state": False, "passive": True},
            True,
        ),
    )

    # Test data for calling the schema with different data sets.
    # (1) test_name: descriptive name
    # (2) constructor_kwargs: arguments for GroupAddressConfigSchema
    # (3) input_data: the data dict to validate
    # (4) expected: the expected result – if vol.Invalid, we expect an exception,
    #               otherwise the validated dict
    CONFIG_CALL_CASES: tuple[tuple[str, dict[str, Any], dict[str, Any], Any], ...] = (
        (
            "dpt_provided_but_no_group_address",
            {"allowed_dpts": (DPTVoltage,)},
            {CONF_DPT: "9.020"},
            vol.Invalid,
        ),
        (
            "write_required_ok",
            {"allowed_dpts": (DPTVoltage,), "write_required": True},
            {CONF_GA_WRITE: "1/2/3", CONF_DPT: "9.020"},
            {
                CONF_GA_WRITE: "1/2/3",
                CONF_DPT: "9.020",
                CONF_GA_STATE: None,
                CONF_GA_PASSIVE: [],
            },
        ),
        (
            "write_required_missing",
            {"allowed_dpts": (DPTVoltage,), "write_required": True},
            {CONF_DPT: "9.020"},  # missing ga_write
            vol.Invalid,
        ),
        (
            "passive_ok",
            {"allowed_dpts": (DPTVoltage,), "passive": True},
            {
                CONF_DPT: "9.020",
                CONF_GA_PASSIVE: ["1/2/3"],
            },
            {
                CONF_DPT: "9.020",
                CONF_GA_PASSIVE: ["1/2/3"],
                CONF_GA_WRITE: None,
                CONF_GA_STATE: None,
            },
        ),
        (
            "dpt_not_allowed",
            {"allowed_dpts": (DPTVoltage,)},
            {CONF_GA_WRITE: "1/2/3", CONF_DPT: "9.001"},
            vol.Invalid,
        ),
    )

    # Test data for serialize method.
    # (1) test_name: descriptive name
    # (2) constructor_kwargs: arguments for GroupAddressConfigSchema
    CONFIG_SERIALIZE_CASES: tuple[tuple[str, dict[str, Any]], ...] = (
        ("default_serialize", {"allowed_dpts": (DPTVoltage,)}),
        (
            "serialize_all_options",
            {
                "allowed_dpts": (DPTVoltage,),
                "write": False,
                "state": True,
                "passive": False,
                "write_required": False,
                "state_required": False,
            },
        ),
    )

    @pytest.mark.parametrize(
        ("test_name", "constructor_kwargs", "expect_error"),
        CONFIG_CONSTRUCTOR_CASES,
        ids=[case[0] for case in CONFIG_CONSTRUCTOR_CASES],
    )
    def test_constructor_validation(
        self,
        hass: HomeAssistant,
        knx: KNXTestKit,
        test_name: str,
        constructor_kwargs: dict[str, Any],
        expect_error: bool,
    ) -> None:
        """Test the validation in __post_init__, ensuring that invalid configurations."""
        if expect_error:
            with pytest.raises(ValueError):
                GroupAddressConfigSchema(**constructor_kwargs)
        else:
            obj = GroupAddressConfigSchema(**constructor_kwargs)
            assert isinstance(obj.schema, vol.Schema), (
                f"Test case '{test_name}' failed: The 'schema' wasn't "
                f"initialized properly."
            )

    @pytest.mark.parametrize(
        ("test_name", "constructor_kwargs", "input_data", "expected"),
        CONFIG_CALL_CASES,
        ids=[case[0] for case in CONFIG_CALL_CASES],
    )
    def test_call_schema(
        self,
        hass: HomeAssistant,
        knx: KNXTestKit,
        test_name: str,
        constructor_kwargs: dict[str, Any],
        input_data: dict[str, Any],
        expected: Any,
    ) -> None:
        """Test the __call__ method of GroupAddressConfigSchema with various inputs.

        - If 'expected' is vol.Invalid, we expect a vol.Invalid exception.
        - Otherwise, we verify the validated dict matches 'expected'.
        """
        # Ensure constructor validation doesn't fail
        instance = GroupAddressConfigSchema(**constructor_kwargs)

        if expected == vol.Invalid:
            with pytest.raises(vol.Invalid):
                instance(input_data)
        else:
            result = instance(input_data)
            assert result == expected, (
                f"Test case '{test_name}' failed: Expected {expected}, got {result}."
            )

    @pytest.mark.parametrize(
        ("test_name", "constructor_kwargs"),
        CONFIG_SERIALIZE_CASES,
        ids=[case[0] for case in CONFIG_SERIALIZE_CASES],
    )
    def test_serialize(
        self,
        hass: HomeAssistant,
        knx: KNXTestKit,
        test_name: str,
        constructor_kwargs: dict[str, Any],
    ) -> None:
        """Test the serialize method of GroupAddressConfigSchema.

        Ensures that the returned dictionary has 'type'='group_address_config'
        and 'properties' as the converted schema.
        """

        def mock_convert(schema: Any) -> Any:
            return "converted_schema"

        instance = GroupAddressConfigSchema(**constructor_kwargs)
        result = GroupAddressConfigSchema.serialize(instance, mock_convert)

        assert isinstance(result, dict), "Serialization result must be a dictionary."
        assert result["type"] == "group_address_config", (
            f"Test case '{test_name}' failed: 'type' is not 'group_address_config'."
        )
        assert result["properties"] == "converted_schema", (
            f"Test case '{test_name}' failed: 'properties' was not 'converted_schema'."
        )
