# ADR-0002 — One installable Python package, not a multi-package monorepo

**Status:** Accepted · 2026-08-07

## Context

The requirements sketch a layout with `apps/cli`, `apps/dashboard`, and a `core/` split into
seven subsystems. Read literally that suggests separately versioned, separately installable
packages with declared inter-dependencies.

FlowForge is currently one developer, one deliverable, zero external consumers of any internal
API.

## Decision

A single distribution, `flowforge`, containing one package `src/flowforge/` with subpackages
matching the conceptual layers. Firmware, hardware, docs, examples, and tests sit beside it in
the repository but are not Python packages.

Layer boundaries are enforced by an **import-direction lint rule** rather than by packaging: a
test walks the module graph and fails if any module imports from a layer above it (per
[architecture.md §4.2](../architecture.md#42-layering)).

## Alternatives considered

**Multi-package monorepo** (`flowforge-core`, `flowforge-cli`, `flowforge-sim`, …) with a
workspace. Real benefits at scale: enforced boundaries, independent release cadence, a slim
install for a device-only deployment. All of them cost something now — version skew between
sibling packages, a release process per package, editable-install friction — and buy nothing
until there is a second consumer. Nothing here is one-way: splitting a package out later is
mechanical, whereas merging prematurely-split packages is also mechanical. Neither is a trap.

**Flat modules, no subpackages.** Would collapse the layering the architecture depends on.

## Consequences

**Good**

- One version number, one lockfile, one `uv run pytest`.
- A contributor clones and runs the whole suite immediately.
- Refactoring across layers is a rename, not a coordinated multi-package release.

**Bad, and accepted**

- Layer boundaries rely on a lint rule rather than the import system. The rule must actually be
  written and run in CI, or the layering rots. It is a milestone item in M0.
- The eventual dashboard will pull the full dependency set. If that becomes a real problem, the
  dashboard is the natural first extraction, and it is the piece least entangled with the rest.
