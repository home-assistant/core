# Prometheus integration

This integration exposes metrics in a Prometheus compatible format.

## Metric naming guidelines

Please follow these guidelines while defining metrics.

* Metric and label names should conform to [Prometheus
  naming guidelines](https://prometheus.io/docs/practices/naming/).
* Domain-specific metrics should have the domain (`sensor`, `switch`,
  `climate`, etc.) as a metric name prefix.
* Enum-like values (e.g. entity state or current mode) should be exported using
  a "boolean" metric (values of 0 or 1) broken down by state/mode (as a metric
  label).
