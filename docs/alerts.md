# CP2 alerts and runbooks

These alerts describe symptoms users can feel. The alert contract is in [`config/alert_rules.yaml`](../config/alert_rules.yaml); all three notify `#k4-l3b-alerts` and are owned by `student-2A202602586`.

<a id="alert-1"></a>
## Alert 1 — UserWaitsTooLong

- **Severity / duration:** warning, P95 response latency above 3,000 ms continuously for 5 minutes.
- **User impact:** most users wait too long to receive an answer. The 3-second limit matches the primary SLO.
- **First checks:**
  1. Open the latency panel and compare P50/P95/P99 with TTFT P95. Check whether all requests or only a few are slow.
  2. Find a slow `response_sent` row in `data/logs.jsonl`; copy its `correlation_id` and confirm the same ID appears in the request row.
  3. Open the matching trace in the personal Langfuse project. Compare retrieval and generation durations and check prompt version metadata.
- **Mitigation:** if retrieval is slow, disable the practice slowdown or restore the healthy retrieval configuration. If generation regressed after a prompt change, roll production back to the last known good version. Record the correlation ID and before/after P95.
- **Owner / channel:** `student-2A202602586` / Slack `#k4-l3b-alerts`.

<a id="alert-2"></a>
## Alert 2 — RequestsFailing

- **Severity / duration:** critical, request failure rate above 2% for 5 minutes.
- **User impact:** users receive errors instead of answers; this consumes the SLO error budget.
- **First checks:**
  1. Check the errors panel and separate API failures from retrieval failures using `error_type` and `tool_success`.
  2. Find a `request_failed` log row and use its `correlation_id` to find the corresponding request and trace.
  3. Read the failing span status and safe error metadata. Confirm whether failures cluster around one prompt/model or affect all requests.
- **Mitigation:** restore the last known good prompt label when failures began after promotion. For an active practice incident, disable that scenario. Retry only after the failing dependency is healthy; do not erase the failed log evidence.
- **Owner / channel:** `student-2A202602586` / Slack `#k4-l3b-alerts`.

<a id="alert-3"></a>
## Alert 3 — RetrievalOftenMisses

- **Severity / duration:** warning, retrieval success below 90% for 10 minutes.
- **User impact:** answers may lack relevant project context and fall back to generic responses.
- **First checks:**
  1. Check the errors panel's retrieval success percentage and count the evaluated retrieval calls; low sample counts can make the percentage noisy.
  2. Inspect safe `tool_name`/`tool_success` log fields and select a failed correlation ID.
  3. Open its trace and verify the retrieval observation status and `doc_count`; do not copy raw user queries into a ticket.
- **Mitigation:** restore the healthy retriever/index configuration, or disable the practice failure scenario. Re-run a small known-good query and confirm success returns above 90% before closing the alert.
- **Owner / channel:** `student-2A202602586` / Slack `#k4-l3b-alerts`.

## Triage order

Start with the dashboard symptom, find one affected request by `correlation_id` in logs, then inspect its trace to locate the slow or failed step. Store only sanitized evidence in the incident note.
