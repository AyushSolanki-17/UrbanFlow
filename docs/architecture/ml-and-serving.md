# ML, serving, and grounded analytics

[Documentation index](../README.md) · [Editable diagram](../diagrams/ml-and-serving.drawio)

**Status:** planned interfaces and evaluation design, with no trained model or published API yet.

## Forecasting and anomalies

Forecast zone demand at +15, +30, and +60 minutes. Begin with a naive/seasonal baseline, then compare XGBoost or LightGBM. Add a small PyTorch model only if the comparison is justified. Inputs may include recent demand, rolling demand, calendar variables, weather, events, traffic, and other service demand.

Train on versioned Gold features and use chronological validation and out-of-time testing. Prevent future leakage in windows, labels, context availability, preprocessing, and joins. Report MAE and RMSE; use MAPE only with explicit treatment of zero or near-zero demand. Report prediction-interval coverage only if intervals are implemented. Slice results by city, zone, service, horizon, and time period where sample sizes support it.

Flink can emit operational anomaly candidates from stateful rolling statistics. The ML layer may produce a more developed anomaly score, severity, and explanation features. Define how candidates and model outputs are related, versioned, and deduplicated before presenting them as one anomaly feed. Thresholds require measured calibration. Travel-time estimation is optional.

## Reproducible lifecycle

Gold snapshot + feature definition + code commit + training configuration → train → evaluate → versioned artifact → serving.

MLflow is planned for the ML stage. Track parameters, metrics, dataset snapshots, feature version, training timestamp, and model version. Define evaluation gates and a rollback procedure before model promotion. Drift monitoring covers features, predictions, and errors once delayed labels become available. Drift should trigger investigation; it does not by itself justify promoting a replacement.

Inference responses should identify the model version, forecast origin, horizon, data freshness, and any uncertainty actually computed. Redis may cache current demand or predictions under documented expiry and version rules. Iceberg retains durable analytical history. A dedicated feature store is deferred until offline/online consistency creates a demonstrated need.

## Proposed API surface

All endpoints below are a design sketch under `/api/v1`, not an existing OpenAPI contract.

| Route | Responsibility |
| --- | --- |
| `/demand` | Current or aggregated zone demand with event-time and freshness metadata |
| `/forecast` | Versioned demand predictions for supported horizons |
| `/anomalies` | Scores/candidates with severity and supporting measurements |
| `/zones` | City-scoped spatial references |
| `/analytics` | Bounded historical queries through approved interfaces |
| `/agent` | Authorized natural-language analytics requests |
| `/health` | Service/dependency health with limited public detail |
| `/metrics` | Operational metrics, protected from public access |

Specify authentication, authorization, validation, pagination, rate limits, timeouts, bounded retries, structured errors, and request IDs when implementing the API. Route Redis reads for current state and Trino queries for historical analytics. Make stale/unavailable results visible instead of fabricating defaults.

Next.js/TypeScript is the intended UI stack; MapLibre or a compatible map library is a candidate. Replay controls must be authorized, rate-bounded, and clearly distinguish event time from wall time. A small public demo may expose curated results without a running distributed ingestion stack.

## Agent execution boundary

1. Authenticate the request and determine the user's permitted tools/data scope.
2. Select structured tools for Trino analytics, forecasts, anomalies, or event/weather context.
3. Validate tool arguments. For SQL, parse and enforce read-only operations, approved catalogs/tables, query budgets, and result limits.
4. Execute with restricted credentials and timeouts; verify the result shape and scope.
5. Explain the returned evidence, including query/reference IDs, filters, time range, and freshness where available.

Read-only database permissions and resource controls are required even when SQL validation passes. Block DDL/DML, unauthorized tables, unbounded scans, and unauthorized tool calls. Treat retrieved text and tool content as untrusted data; it must not grant permissions or override the tool policy. Record auditable tool usage without logging secrets.

The LLM is an explanation and tool-selection layer. Empty data, timeouts, stale results, or unsupported questions must be stated as such. Correlation with events/weather must not become an unsupported causal claim.

## Evaluation

Maintain fixed cases for aggregation, time and zone comparisons, anomaly and forecast explanations, multi-source questions, invalid/out-of-scope requests, SQL injection, and prompt injection. Each case records expected intent, tools, SQL constraints, and result properties.

Measure tool-selection accuracy, SQL validity, execution success, grounded-answer rate, unsupported claims, latency, and applicable cost. Report model quality and agent quality separately. No results are claimed until experiments run.
