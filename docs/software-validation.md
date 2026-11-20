# Software foundation validation

The software-only CI workflow is `.github/workflows/ci.yml`. Pushes and pull
requests run the same checks on Ubuntu with Python 3.11 and 3.13:

```bash
uv sync --locked
uv run --locked pytest
uv run --locked mypy
uv run --locked ruff check .
uv run --locked ruff format --check src tests
uv build
```

The workflow selects Python through setup-uv and pins uv 0.11.24, matching the
local validation tool. Both actions are pinned by commit. Workflow permissions
are contents-read only, checkout credentials are not retained, and there are no
publish, deployment, hardware or external-model steps. Builds stay on the runner.
Sources: [setup-uv](https://github.com/astral-sh/setup-uv) and
[checkout](https://github.com/actions/checkout). A committed workflow is not
evidence that a particular run passed; inspect the run for the delivered SHA.

## Static layering guard

`tests/architecture/test_import_direction.py` implements ADR-0002 and architecture
section 4.2 without importing or executing source modules. It walks every Python
file under `src/flowforge`, including nested packages and imports inside
conditional blocks. Explicit imports must point to the same or a lower tier.
Relative imports and `from flowforge import submodule` forms are resolved against
the source map, so an upward edge cannot hide behind those forms.

The root facade and Quantity belong to the leaf tier. New top-level package
modules fail until deliberately classified; update the architecture and guard
together if a new layer is needed. Scientific layers (signal, aero, analysis,
report) also fail when their dependency graph reaches devices indirectly. This
preserves their hardware-free boundary even through lower-level helpers.

The guard covers explicit Python imports. Direct `__import__` and attribute
`import_module` calls require review and fail. It is a development check, not a
security sandbox: disguised dynamic imports, runtime code generation, external
package side effects and actual device I/O are not exhaustively detected.
Handwritten synthetic graphs prove rejection of invalid imports; current-source
inspection fails if no Python files are found.

## Scope and limitations

Formatting checks intentionally cover source and tests. Existing Markdown design
examples are not reformatted by this change. Strict mypy covers production source;
pytest exercises the architecture guard and its fixtures. Future device/scientific
implementations need their own behavioral and physical acceptance checks.

This is a further partial M0 delivery. Explicit units-edge conversions are covered by reference, round-trip, domain
and overflow tests. Errors/logging helpers remain TODO.
Passing checks do not demonstrate calibrated measurements, a simulator, instrument
CLI, serial control, cross-platform hardware support or the full V0 workflow.
