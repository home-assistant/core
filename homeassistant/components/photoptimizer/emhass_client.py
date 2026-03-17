"""Client for EMHASS communication."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .models import EmhassExecutionResult, OptimizationInputs, PublishedEntityState

_LOGGER = logging.getLogger(__name__)

DEFAULT_BATTERY_CHARGE_POWER_MAX = 1000.0
DEFAULT_BATTERY_DISCHARGE_POWER_MAX = 1000.0
DEFAULT_BATTERY_EFFICIENCY = 0.95
DEFAULT_BATTERY_MAXIMUM_STATE_OF_CHARGE = 0.9


class EmhassClient:
    """Own the complete EMHASS workflow for one Photoptimizer config entry.

    The coordinator prepares neutral aggregated inputs only. This client is the
    only place that knows how those inputs map to EMHASS runtimeparams, which
    actions need to be called, and where the published EMHASS entities live.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        token: str | None = None,
        *,
        battery_capacity_kwh: float,
        battery_efficiency: float,
        battery_soc_reserve: float,
        wear_cost_per_kwh: float,
    ) -> None:
        """Store session, base URL, publish targets, and runtime defaults."""
        self._hass = hass
        self._url = url.rstrip("/")
        self._session = async_get_clientsession(hass)
        self._token = token
        self._battery_charge_power_max = DEFAULT_BATTERY_CHARGE_POWER_MAX
        self._battery_discharge_power_max = DEFAULT_BATTERY_DISCHARGE_POWER_MAX
        self._battery_nominal_energy_capacity = (
            battery_capacity_kwh * 1000.0 if battery_capacity_kwh > 0 else 5000.0
        )
        self._battery_efficiency = min(
            max(battery_efficiency, 0.01),
            1.0,
        )
        self._battery_soc_reserve = battery_soc_reserve
        self._wear_cost_per_kwh = wear_cost_per_kwh

        # Use documented EMHASS default entity IDs.
        self._published_entities: dict[str, dict[str, str]] = {
            "pv_forecast": {
                "entity_id": "sensor.p_pv_forecast",
                "unit_of_measurement": "W",
                "friendly_name": "PV Power Forecast",
            },
            "load_forecast": {
                "entity_id": "sensor.p_load_forecast",
                "unit_of_measurement": "W",
                "friendly_name": "Load Power Forecast",
            },
            "battery_forecast": {
                "entity_id": "sensor.p_batt_forecast",
                "unit_of_measurement": "W",
                "friendly_name": "Battery Power Forecast",
            },
            "battery_soc_forecast": {
                "entity_id": "sensor.soc_batt_forecast",
                "unit_of_measurement": "%",
                "friendly_name": "Battery SOC Forecast",
            },
            "grid_forecast": {
                "entity_id": "sensor.p_grid_forecast",
                "unit_of_measurement": "W",
                "friendly_name": "Grid Power Forecast",
            },
            "unit_load_cost": {
                "entity_id": "sensor.unit_load_cost",
                "unit_of_measurement": "currency/kWh",
                "friendly_name": "Unit Load Cost",
            },
            "unit_prod_price": {
                "entity_id": "sensor.unit_prod_price",
                "unit_of_measurement": "currency/kWh",
                "friendly_name": "Unit Prod Price",
            },
            "cost_fun": {
                "entity_id": "sensor.total_cost_fun_value",
                "unit_of_measurement": "currency",
                "friendly_name": "Total cost function value",
            },
            "optim_status": {
                "entity_id": "sensor.optim_status",
                "unit_of_measurement": "",
                "friendly_name": "EMHASS optimization status",
            },
        }

    def _headers(self) -> dict[str, str]:
        """Return headers for EMHASS HTTP requests."""
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _async_check_url(self, url: str, label: str) -> bool:
        """Lightweight reachability check before hitting EMHASS."""
        try:
            async with self._session.get(
                url,
                headers=self._headers(),
                timeout=ClientTimeout(total=5),
            ) as response:
                if response.status < 500:
                    return True
                _LOGGER.error("%s unreachable (%s)", label, response.status)
        except ClientError as err:
            _LOGGER.error("%s connection error at %s: %s", label, url, err)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("%s unexpected error at %s: %s", label, url, err)
        return False

    async def _async_post_action(
        self,
        action: str,
        payload: dict[str, Any],
        *,
        timeout: int,
    ) -> dict[str, Any] | None:
        """Post one action to the EMHASS web server."""
        endpoint = f"{self._url}/action/{action}"

        try:
            async with self._session.post(
                endpoint,
                json=payload,
                headers=self._headers(),
                timeout=ClientTimeout(total=timeout),
            ) as response:
                text = await response.text()
                if response.status not in (200, 201):
                    if response.status >= 500:
                        _LOGGER.error(
                            "EMHASS internal error at %s. Check the EMHASS add-on logs for the Python traceback",
                            endpoint,
                        )
                        _LOGGER.error("EMHASS error %s: %s", response.status, text)
                        return None
                    # 400 from publish-data means "published with warnings" — the
                    # response body is a JSON array of log lines. Log it and continue.
                    _LOGGER.warning(
                        "EMHASS %s returned %s (treating as partial success): %s",
                        action,
                        response.status,
                        text,
                    )

                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    data = await response.json()
                    if isinstance(data, dict):
                        _LOGGER.debug("EMHASS %s response keys: %s", action, list(data))
                        return data
                    return {"data": data, "status": response.status}

                _LOGGER.debug("EMHASS %s success %s: %s", action, response.status, text)
                return {"message": text, "status": response.status}
        except ClientError as err:
            _LOGGER.error("EMHASS connection error at %s: %s", endpoint, err)
            return None
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("EMHASS unexpected error at %s: %s", endpoint, err)
            return None

    def _build_runtimeparams(self, inputs: OptimizationInputs) -> dict[str, Any]:
        """Translate aggregated coordinator data into EMHASS runtimeparams."""
        runtimeparams: dict[str, Any] = {
            "pv_power_forecast": [bucket.pv * 1000.0 for bucket in inputs.timeline],
            "load_power_forecast": [bucket.load * 1000.0 for bucket in inputs.timeline],
            "load_cost_forecast": [bucket.price for bucket in inputs.timeline],
            # Future enhancement: replace the fixed 90% export tariff heuristic
            # with a dedicated export price source exposed by the integration.
            "prod_price_forecast": [bucket.price * 0.9 for bucket in inputs.timeline],
            # Explicitly enable battery mode and provide plant parameters so the
            # optimization does not depend on static EMHASS config defaults.
            "set_use_pv": True,
            "set_use_battery": True,
            "battery_discharge_power_max": self._battery_discharge_power_max,
            "battery_charge_power_max": self._battery_charge_power_max,
            "battery_discharge_efficiency": self._battery_efficiency,
            "battery_charge_efficiency": self._battery_efficiency,
            "battery_nominal_energy_capacity": self._battery_nominal_energy_capacity,
            "prediction_horizon": inputs.prediction_horizon,
            "optimization_time_step": inputs.optimization_time_step_minutes,
            "soc_init": inputs.battery_soc,
            "soc_final": inputs.battery_soc,
            "battery_target_state_of_charge": inputs.battery_soc,
            "battery_minimum_state_of_charge": self._battery_soc_reserve,
            "battery_maximum_state_of_charge": DEFAULT_BATTERY_MAXIMUM_STATE_OF_CHARGE,
            "number_of_deferrable_loads": 0,
            "continual_publish": False,
        }

        if self._wear_cost_per_kwh > 0:
            runtimeparams["weight_battery_charge"] = self._wear_cost_per_kwh
            runtimeparams["weight_battery_discharge"] = self._wear_cost_per_kwh

        # Future enhancement: map real inverter and battery power limits once the
        # integration exposes charge/discharge capability data.
        return runtimeparams

    def _build_publish_payload(
        self, optimization_time_step_minutes: int
    ) -> dict[str, Any]:
        """Build the publish-data payload with custom entity targets."""
        return {
            # Both must match the values used during naive-mpc-optim so that
            # publish-data reads opt_res_latest.csv with the correct frequency
            # and does not try to publish deferrable load columns that don't exist.
            "optimization_time_step": optimization_time_step_minutes,
            "number_of_deferrable_loads": 0,
            "custom_pv_forecast_id": self._published_entities["pv_forecast"],
            "custom_load_forecast_id": self._published_entities["load_forecast"],
            "custom_batt_forecast_id": self._published_entities["battery_forecast"],
            "custom_batt_soc_forecast_id": self._published_entities[
                "battery_soc_forecast"
            ],
            "custom_grid_forecast_id": self._published_entities["grid_forecast"],
            "custom_unit_load_cost_id": self._published_entities["unit_load_cost"],
            "custom_unit_prod_price_id": self._published_entities["unit_prod_price"],
            "custom_cost_fun_id": self._published_entities["cost_fun"],
            "custom_optim_status_id": self._published_entities["optim_status"],
        }

    def _read_published_entities(self) -> dict[str, PublishedEntityState]:
        """Read the EMHASS-published entities from the local Home Assistant state machine."""
        snapshots: dict[str, PublishedEntityState] = {}

        # Future enhancement: if EMHASS publishes into a different Home Assistant
        # instance, replace this local state lookup with a remote bridge.
        for key, descriptor in self._published_entities.items():
            entity_id = descriptor["entity_id"]
            state = self._hass.states.get(entity_id)
            snapshots[key] = PublishedEntityState(
                entity_id=entity_id,
                state=None if state is None else state.state,
                attributes={} if state is None else dict(state.attributes),
            )

        return snapshots

    def _log_published_entities(
        self, published_entities: dict[str, PublishedEntityState]
    ) -> None:
        """Log a compact summary of the entities published by EMHASS."""
        _LOGGER.debug(
            "EMHASS published entities:\n%s",
            "\n".join(
                f"  {key}: {entity.state} ({entity.entity_id})"
                for key, entity in published_entities.items()
            ),
        )

    async def async_run_naive_mpc(
        self, inputs: OptimizationInputs
    ) -> EmhassExecutionResult | None:
        """Run one EMHASS naive MPC cycle and publish the resulting entities."""
        if not await self._async_check_url(self._url, "EMHASS base"):
            return None

        runtimeparams = self._build_runtimeparams(inputs)
        optimization_response = await self._async_post_action(
            "naive-mpc-optim",
            runtimeparams,
            timeout=60,
        )
        if optimization_response is None:
            return None

        publish_response = await self._async_post_action(
            "publish-data",
            self._build_publish_payload(inputs.optimization_time_step_minutes),
            timeout=30,
        )
        if publish_response is None:
            return None

        await self._hass.async_block_till_done()
        published_entities = self._read_published_entities()

        self._log_published_entities(published_entities)

        return EmhassExecutionResult(
            runtimeparams=runtimeparams,
            optimization_response=optimization_response,
            publish_response=publish_response,
            published_entities=published_entities,
        )
