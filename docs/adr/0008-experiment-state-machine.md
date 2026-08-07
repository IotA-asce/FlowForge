# ADR-0008 — Experiments are an explicit state machine with a universal abort path

**Status:** Accepted · 2026-08-07

## Context

An experiment sets a fan duty, waits for the flow to settle, samples, moves on, and eventually
analyses and stops. The natural implementation is a `for` loop with `sleep()` calls. That
implementation cannot answer: what state was it in when it failed; is it safe to abort here;
what did it actually do at 14:26:31; can this run be resumed or trusted.

The requirements name the state machine explicitly and require experiments to fail safely.

## Decision

An explicit state machine with a closed set of states and a closed set of failure reasons.
States: `CREATED`, `VALIDATING`, `CONNECTING`, `ZEROING`, `BASELINE`, `SETTING_CONDITION`,
`STABILISING`, `SAMPLING`, `STOPPING`, `ANALYSING`, `COMPLETED`, `ABORTING`, `FAILED`,
`ABORTED`.

Failure reasons: `SENSOR_FAILURE`, `DEVICE_DISCONNECTED`, `AIRFLOW_UNSTABLE`,
`SPEED_UNREACHABLE`, `CALIBRATION_MISSING`, `CALIBRATION_EXPIRED`, `OVERLOAD`, `USER_ABORTED`,
`HOST_ERROR`.

Enforced invariants:

1. Every transition is appended to `raw/events.jsonl` **before** the action it announces, and
   flushed. A crash leaves evidence of intent, not just of outcome.
2. `ABORTING` is reachable from every state, and its **first** action is `fan.stop()` — before
   logging, before teardown, before anything that could itself fail.
3. Raw sample writing begins at `CONNECTING` and ends at `STOPPING`, covering stabilisation and
   transitions, not merely the sample windows.
4. `ANALYSING` reads only from files already on disk. If it fails, the run directory is still a
   complete, re-analysable record and `flowforge analyze` can retry offline.
5. `SETTING_CONDITION` is parameter-agnostic — `airspeed` today, `angle` in V2 — so the sweep
   engine does not need rewriting for a new sweep parameter.

Both properties 2 and the reachability of every failure reason are covered by property-based
tests over the full state set, not by example tests.

## Alternatives considered

**Sequential code with sleeps.** Rejected as above: unobservable, unresumable, and unsafe to
abort from an arbitrary point.

**A generic workflow/DAG library.** Heavy machinery for one linear-with-a-loop process, and it
would obscure the safety invariants that are the reason for having a state machine at all.

**`asyncio` with cancellation as the abort mechanism.** Elegant in principle. Rejected because
cancellation semantics in Python are subtle enough that "did the fan actually stop?" becomes a
question about task scheduling — and that is precisely the question that must never be subtle.
The abort path is explicit and synchronous.

**Persisting state for mid-run resume.** Attractive, but a resumed sweep has a different thermal
history and a different zero, so its points are not comparable with the pre-interruption ones.
An interrupted run is `ABORTED` and its partial data is retained for inspection, not resumed.

## Consequences

**Good**

- Every run has a complete, timestamped narrative of what the engine did and why it stopped.
- The abort path is one code path, tested from every state, rather than scattered cleanup.
- Statistical stabilisation (V0 optional, later default) and angle sweeps (V2) slot into
  existing states rather than requiring new control flow.

**Bad, and accepted**

- More code than a loop with sleeps, and more ceremony for the simple happy path.
- Partial runs still produce a directory. That is intentional — a failed run's raw data is often
  the most informative data there is — but it means run listings must distinguish `COMPLETED`
  from `ABORTED`/`FAILED` prominently, which the CLI does.
