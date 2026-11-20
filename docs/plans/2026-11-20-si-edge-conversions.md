# SI Edge Conversions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver the accepted M0 units leaf with explicit conversion helpers for config/display edges.

**Architecture:** Pure dependency-free functions in flowforge.units for mm/metres, g/kg, percent/fraction and Celsius/kelvin. No implicit Quantity conversion or uncertainty propagation, no registry or device I/O. Follow architecture section11:SI internally, conversion at I/O edges only.

**Tech Stack:** Python3.11+, stdlib math; existing locked pytest/mypy/ruff/uv tooling.

---

1. Add tests/unit/test_units.py with fixed reference values, round trips, signed linear inputs, zero/absolute-zero temperatures, domain failures, nonfinite/bool/string rejection and finite-output overflow. Run locked pytest and confirm missing-module failure first.
2. Implement eight named functions: mm_to_m/m_to_mm,g_to_kg/kg_to_g,percent_to_fraction/fraction_to_percent,celsius_to_kelvin/kelvin_to_celsius. Validate numeric finite input and output; reject booleans/types explicitly, negative kelvin/below-absolute-zero Celsius. Linear unit helpers are not channel-specific validators (percent is not constrained to0..100).
3. Document formulas, domain and floating-point/uncertainty limits in docs/units.md; update current M0/README/validation docs, leaving errors/logging and later milestones TODO. No new dependencies or root facade re-exports.
4. Run full locked pytest,strict mypy,uncached Ruff,format,diff check,build and fresh-wheel no-dependency conversion smoke. Scan staged source, commit/push feature, verify actual Ubuntu3.11/3.13 CI before merging main. Verify remote SHAs and unchanged existing visibility; no release/deployment.
5. Update shared records and existing FlowForge memory, preserve all child memory indexes on rebuild, release own lock. Execute directly under the scheduled mandate; no separate execution handoff.

Acceptance: exact documented scale/offset relations verified within float tolerance; finite/domain guards;existing Quantity behavior and architecture tests preserved;full validation/native CI pass. This is only the M0 units slice, not full M0 or a physical accuracy claim.
