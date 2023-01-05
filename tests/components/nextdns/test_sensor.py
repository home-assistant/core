"""Test sensor of NextDNS integration."""
from datetime import timedelta
from unittest.mock import patch

from nextdns import ApiError

from homeassistant.components.nextdns.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorStateClass,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import DNSSEC, ENCRYPTION, IP_VERSIONS, PROTOCOLS, STATUS, init_integration

from tests.common import async_fire_time_changed


async def test_sensor(hass: HomeAssistant) -> None:
    """Test states of sensors."""
    registry = er.async_get(hass)

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_doh_queries",
        suggested_object_id="fake_profile_dns_over_https_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_doh3_queries",
        suggested_object_id="fake_profile_dns_over_http_3_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_doh_queries_ratio",
        suggested_object_id="fake_profile_dns_over_https_queries_ratio",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_doh3_queries_ratio",
        suggested_object_id="fake_profile_dns_over_http_3_queries_ratio",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_doq_queries",
        suggested_object_id="fake_profile_dns_over_quic_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_doq_queries_ratio",
        suggested_object_id="fake_profile_dns_over_quic_queries_ratio",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_dot_queries",
        suggested_object_id="fake_profile_dns_over_tls_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_dot_queries_ratio",
        suggested_object_id="fake_profile_dns_over_tls_queries_ratio",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_not_validated_queries",
        suggested_object_id="fake_profile_dnssec_not_validated_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_validated_queries",
        suggested_object_id="fake_profile_dnssec_validated_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_validated_queries_ratio",
        suggested_object_id="fake_profile_dnssec_validated_queries_ratio",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_encrypted_queries",
        suggested_object_id="fake_profile_encrypted_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_encrypted_queries_ratio",
        suggested_object_id="fake_profile_encrypted_queries_ratio",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_ipv4_queries",
        suggested_object_id="fake_profile_ipv4_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_ipv6_queries",
        suggested_object_id="fake_profile_ipv6_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_ipv6_queries_ratio",
        suggested_object_id="fake_profile_ipv6_queries_ratio",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_tcp_queries",
        suggested_object_id="fake_profile_tcp_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_tcp_queries_ratio",
        suggested_object_id="fake_profile_tcp_queries_ratio",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_udp_queries",
        suggested_object_id="fake_profile_udp_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_udp_queries_ratio",
        suggested_object_id="fake_profile_udp_queries_ratio",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_unencrypted_queries",
        suggested_object_id="fake_profile_unencrypted_queries",
        disabled_by=None,
    )

    await init_integration(hass)

    state = hass.states.get("sensor.fake_profile_dns_queries")
    assert state
    assert state.state == "100"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_dns_queries")
    assert entry
    assert entry.unique_id == "xyz12_all_queries"

    state = hass.states.get("sensor.fake_profile_dns_queries_blocked")
    assert state
    assert state.state == "20"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_dns_queries_blocked")
    assert entry
    assert entry.unique_id == "xyz12_blocked_queries"

    state = hass.states.get("sensor.fake_profile_dns_queries_blocked_ratio")
    assert state
    assert state.state == "20.0"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.fake_profile_dns_queries_blocked_ratio")
    assert entry
    assert entry.unique_id == "xyz12_blocked_queries_ratio"

    state = hass.states.get("sensor.fake_profile_dns_queries_relayed")
    assert state
    assert state.state == "10"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_dns_queries_relayed")
    assert entry
    assert entry.unique_id == "xyz12_relayed_queries"

    state = hass.states.get("sensor.fake_profile_dns_over_https_queries")
    assert state
    assert state.state == "20"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_dns_over_https_queries")
    assert entry
    assert entry.unique_id == "xyz12_doh_queries"

    state = hass.states.get("sensor.fake_profile_dns_over_https_queries_ratio")
    assert state
    assert state.state == "17.4"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.fake_profile_dns_over_https_queries_ratio")
    assert entry
    assert entry.unique_id == "xyz12_doh_queries_ratio"

    state = hass.states.get("sensor.fake_profile_dns_over_http_3_queries")
    assert state
    assert state.state == "15"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_dns_over_http_3_queries")
    assert entry
    assert entry.unique_id == "xyz12_doh3_queries"

    state = hass.states.get("sensor.fake_profile_dns_over_http_3_queries_ratio")
    assert state
    assert state.state == "13.0"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.fake_profile_dns_over_http_3_queries_ratio")
    assert entry
    assert entry.unique_id == "xyz12_doh3_queries_ratio"

    state = hass.states.get("sensor.fake_profile_dns_over_quic_queries")
    assert state
    assert state.state == "10"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_dns_over_quic_queries")
    assert entry
    assert entry.unique_id == "xyz12_doq_queries"

    state = hass.states.get("sensor.fake_profile_dns_over_quic_queries_ratio")
    assert state
    assert state.state == "8.7"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.fake_profile_dns_over_quic_queries_ratio")
    assert entry
    assert entry.unique_id == "xyz12_doq_queries_ratio"

    state = hass.states.get("sensor.fake_profile_dns_over_tls_queries")
    assert state
    assert state.state == "30"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_dns_over_tls_queries")
    assert entry
    assert entry.unique_id == "xyz12_dot_queries"

    state = hass.states.get("sensor.fake_profile_dns_over_tls_queries_ratio")
    assert state
    assert state.state == "26.1"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.fake_profile_dns_over_tls_queries_ratio")
    assert entry
    assert entry.unique_id == "xyz12_dot_queries_ratio"

    state = hass.states.get("sensor.fake_profile_dnssec_not_validated_queries")
    assert state
    assert state.state == "25"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_dnssec_not_validated_queries")
    assert entry
    assert entry.unique_id == "xyz12_not_validated_queries"

    state = hass.states.get("sensor.fake_profile_dnssec_validated_queries")
    assert state
    assert state.state == "75"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_dnssec_validated_queries")
    assert entry
    assert entry.unique_id == "xyz12_validated_queries"

    state = hass.states.get("sensor.fake_profile_dnssec_validated_queries_ratio")
    assert state
    assert state.state == "75.0"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.fake_profile_dnssec_validated_queries_ratio")
    assert entry
    assert entry.unique_id == "xyz12_validated_queries_ratio"

    state = hass.states.get("sensor.fake_profile_encrypted_queries")
    assert state
    assert state.state == "60"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_encrypted_queries")
    assert entry
    assert entry.unique_id == "xyz12_encrypted_queries"

    state = hass.states.get("sensor.fake_profile_unencrypted_queries")
    assert state
    assert state.state == "40"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_unencrypted_queries")
    assert entry
    assert entry.unique_id == "xyz12_unencrypted_queries"

    state = hass.states.get("sensor.fake_profile_encrypted_queries_ratio")
    assert state
    assert state.state == "60.0"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.fake_profile_encrypted_queries_ratio")
    assert entry
    assert entry.unique_id == "xyz12_encrypted_queries_ratio"

    state = hass.states.get("sensor.fake_profile_ipv4_queries")
    assert state
    assert state.state == "90"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_ipv4_queries")
    assert entry
    assert entry.unique_id == "xyz12_ipv4_queries"

    state = hass.states.get("sensor.fake_profile_ipv6_queries")
    assert state
    assert state.state == "10"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_ipv6_queries")
    assert entry
    assert entry.unique_id == "xyz12_ipv6_queries"

    state = hass.states.get("sensor.fake_profile_ipv6_queries_ratio")
    assert state
    assert state.state == "10.0"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.fake_profile_ipv6_queries_ratio")
    assert entry
    assert entry.unique_id == "xyz12_ipv6_queries_ratio"

    state = hass.states.get("sensor.fake_profile_tcp_queries")
    assert state
    assert state.state == "0"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_tcp_queries")
    assert entry
    assert entry.unique_id == "xyz12_tcp_queries"

    state = hass.states.get("sensor.fake_profile_tcp_queries_ratio")
    assert state
    assert state.state == "0.0"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.fake_profile_tcp_queries_ratio")
    assert entry
    assert entry.unique_id == "xyz12_tcp_queries_ratio"

    state = hass.states.get("sensor.fake_profile_udp_queries")
    assert state
    assert state.state == "40"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_udp_queries")
    assert entry
    assert entry.unique_id == "xyz12_udp_queries"

    state = hass.states.get("sensor.fake_profile_udp_queries_ratio")
    assert state
    assert state.state == "34.8"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.fake_profile_udp_queries_ratio")
    assert entry
    assert entry.unique_id == "xyz12_udp_queries_ratio"


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    registry = er.async_get(hass)

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_doh_queries",
        suggested_object_id="fake_profile_dns_over_https_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_validated_queries",
        suggested_object_id="fake_profile_dnssec_validated_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_encrypted_queries",
        suggested_object_id="fake_profile_encrypted_queries",
        disabled_by=None,
    )
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_ipv4_queries",
        suggested_object_id="fake_profile_ipv4_queries",
        disabled_by=None,
    )

    await init_integration(hass)

    state = hass.states.get("sensor.fake_profile_dns_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "100"

    state = hass.states.get("sensor.fake_profile_dns_over_https_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "20"

    state = hass.states.get("sensor.fake_profile_dnssec_validated_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "75"

    state = hass.states.get("sensor.fake_profile_encrypted_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "60"

    state = hass.states.get("sensor.fake_profile_ipv4_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "90"

    future = utcnow() + timedelta(minutes=10)
    with patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_status",
        side_effect=ApiError("API Error"),
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_dnssec",
        side_effect=ApiError("API Error"),
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_encryption",
        side_effect=ApiError("API Error"),
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_ip_versions",
        side_effect=ApiError("API Error"),
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_protocols",
        side_effect=ApiError("API Error"),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.fake_profile_dns_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.fake_profile_dns_over_https_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.fake_profile_dnssec_validated_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.fake_profile_encrypted_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.fake_profile_ipv4_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=20)
    with patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_status",
        return_value=STATUS,
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_encryption",
        return_value=ENCRYPTION,
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_dnssec",
        return_value=DNSSEC,
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_ip_versions",
        return_value=IP_VERSIONS,
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_protocols",
        return_value=PROTOCOLS,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.fake_profile_dns_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "100"

    state = hass.states.get("sensor.fake_profile_dns_over_https_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "20"

    state = hass.states.get("sensor.fake_profile_dnssec_validated_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "75"

    state = hass.states.get("sensor.fake_profile_encrypted_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "60"

    state = hass.states.get("sensor.fake_profile_ipv4_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "90"
