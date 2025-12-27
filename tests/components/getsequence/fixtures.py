"""Test fixtures for Sequence integration testing."""

from typing import Any


def get_mock_sequence_data() -> dict[str, Any]:
    """Mock Sequence API data with comprehensive account types for testing."""
    return {
        "data": {
            "accounts": [
                # Pod accounts
                {
                    "id": "5579244",
                    "name": "Test Pod 1",
                    "balance": {"amountInDollars": 1000.0, "error": None},
                    "type": "Pod",
                },
                {
                    "id": "5579245",
                    "name": "Test Pod 2",
                    "balance": {"amountInDollars": 500.0, "error": None},
                    "type": "Pod",
                },
                # Income source accounts
                {
                    "id": "5579246",
                    "name": "Income Account 1",
                    "balance": {"amountInDollars": 2000.0, "error": None},
                    "type": "Income Source",
                },
                {
                    "id": "5579250",
                    "name": "Income Account 2",
                    "balance": {"amountInDollars": 1500.0, "error": None},
                    "type": "Income Source",
                },
                # Native liability accounts (should be included in liability total)
                {
                    "id": "5579247",
                    "name": "Credit Card",
                    "balance": {"amountInDollars": -850.0, "error": None},
                    "type": "Liability",
                },
                # Native investment accounts (should be included in investment total)
                {
                    "id": "5579248",
                    "name": "401k Account",
                    "balance": {"amountInDollars": 50000.0, "error": None},
                    "type": "Investment",
                },
                # External accounts (can be categorized via options)
                {
                    "id": "5579249",
                    "name": "External Bank",
                    "balance": {"amountInDollars": 1500.0, "error": None},
                    "type": "External",
                },
                {
                    "id": "5579251",
                    "name": "Mortgage Account",
                    "balance": {"amountInDollars": -250000.0, "error": None},
                    "type": "External",
                },
                {
                    "id": "5579252",
                    "name": "Brokerage Account",
                    "balance": {"amountInDollars": 75000.0, "error": None},
                    "type": "External",
                },
            ]
        }
    }


def get_mock_sequence_data_with_categorized_externals() -> dict[str, Any]:
    """Mock data with manually categorized external accounts via options."""
    # This would be combined with config entry options like:
    # options = {
    #     "liability_accounts": ["5579251"],  # Mortgage Account
    #     "investment_accounts": ["5579252"],  # Brokerage Account
    # }
    return get_mock_sequence_data()


def get_mock_sequence_data_with_errors() -> dict[str, Any]:
    """Mock data with some account balance errors for testing error handling."""
    return {
        "data": {
            "accounts": [
                {
                    "id": "5579244",
                    "name": "Test Pod 1",
                    "balance": {"amountInDollars": 1000.0, "error": None},
                    "type": "Pod",
                },
                {
                    "id": "5579245",
                    "name": "Test Pod 2",
                    "balance": {"amountInDollars": None, "error": "Connection timeout"},
                    "type": "Pod",
                },
                {
                    "id": "5579246",
                    "name": "Income Account",
                    "balance": {"amountInDollars": 2000.0, "error": None},
                    "type": "Income Source",
                },
            ]
        }
    }


def get_mock_sequence_cash_flow_data() -> list[dict[str, Any]]:
    """Mock cash flow tracking data for utility meter tests."""
    return [
        # Initial state
        {
            "data": {
                "accounts": [
                    {
                        "id": "5579244",
                        "name": "Test Pod 1",
                        "balance": {"amountInDollars": 1000.0, "error": None},
                        "type": "Pod",
                    },
                    {
                        "id": "5579246",
                        "name": "Income Account",
                        "balance": {"amountInDollars": 2000.0, "error": None},
                        "type": "Income Source",
                    },
                    {
                        "id": "5579249",
                        "name": "External Bank",
                        "balance": {"amountInDollars": 1500.0, "error": None},
                        "type": "External",
                    },
                ]
            }
        },
        # After positive cash flow
        {
            "data": {
                "accounts": [
                    {
                        "id": "5579244",
                        "name": "Test Pod 1",
                        "balance": {"amountInDollars": 1200.0, "error": None},  # +200
                        "type": "Pod",
                    },
                    {
                        "id": "5579246",
                        "name": "Income Account",
                        "balance": {"amountInDollars": 2300.0, "error": None},  # +300
                        "type": "Income Source",
                    },
                    {
                        "id": "5579249",
                        "name": "External Bank",
                        "balance": {
                            "amountInDollars": 1450.0,
                            "error": None,
                        },  # -50 (negative flow, should not add)
                        "type": "External",
                    },
                ]
            }
        },
        # After more positive cash flow
        {
            "data": {
                "accounts": [
                    {
                        "id": "5579244",
                        "name": "Test Pod 1",
                        "balance": {
                            "amountInDollars": 1400.0,
                            "error": None,
                        },  # +200 more
                        "type": "Pod",
                    },
                    {
                        "id": "5579246",
                        "name": "Income Account",
                        "balance": {
                            "amountInDollars": 2400.0,
                            "error": None,
                        },  # +100 more
                        "type": "Income Source",
                    },
                    {
                        "id": "5579249",
                        "name": "External Bank",
                        "balance": {
                            "amountInDollars": 1550.0,
                            "error": None,
                        },  # +100 (positive flow)
                        "type": "External",
                    },
                ]
            }
        },
    ]
