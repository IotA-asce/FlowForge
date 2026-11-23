# Errors and structured logging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the queued M0 error/logging foundation without implementing run storage or devices.

**Architecture:** Add leaf modules errors and logging using only Python stdlib. Explicitly configure the flowforge logger with caller-owned console and event streams; no import-time setup or root logger mutation. JSON records nest user fields to prevent reserved-key collisions.

**Tech Stack:** Python3.11+,stdlib logging/json,existing pytest/mypy/ruff/uv and UbuntuCI.

---

### Task 1: Behavioral tests

Create tests/unit/test_logging.py. Assert FlowForgeError is catchable across ConfigurationError,strict JSON lines preserve nested fields and escaped newlines,DEBUG reaches event stream only,exception details survive,invalid JSON fields fail before logging,repeated setup emits once,preserves unrelated handlers and leaves streams open. A subprocess proves imports do not alter logging configuration. Run uv run --locked pytest tests/unit/test_logging.py;expect missing-module failure before implementation.

### Task 2: Minimal leaves

Create src/flowforge/errors.py with FlowForgeError and ConfigurationError. Create src/flowforge/logging.py with JsonFormatter,configure_logging(events,console=None),close_logging() and log_event(logger,event,level=INFO,**fields). Emit timestamp/level/logger/event/fields and optional exception. Pre-serialize fields with allow_nan=False so invalid inputs fail synchronously and caller mutation cannot alter records. Use private owned StreamHandlers for replacement/cleanup;never close caller streams or remove foreign handlers. Console threshold INFO,event threshold DEBUG. No filesystem opens,no automatic sample logging,no run-directory lifecycle.

### Task 3: Verification and delivery

Run uv sync --locked --python3.11;uv run --locked pytest;uv run --locked mypy;uv run --locked ruff check .;uv run --locked ruff format --check src tests;uv build. Install wheel into fresh temporary venv and exercise both sinks/error handling. Update docs/errors-logging.md,README.md,docs/v0-plan.md and docs/software-validation.md. Review explicit staged paths and Gitleaks;commit,merge main,push and verify remoteSHAs and actualUbuntu3.11/3.13CI. Do not claim later simulator,CLI,storage or hardware milestones. Persist portfolio state and receipt.
