# M0 subset: metrology primitives

Implement the accepted single Python 3.11+ src package and dependency-free provenance/Quantity leaves from ADR-0012. Preserve all five tags, automatic assumption/estimate demotion for explicit computed construction, explicit standard uncertainty and coverage factor, central two-significant-figure expanded-uncertainty formatting, mandatory provenance, and unknown/low-SNR warnings. Test documented examples, rounding carry, all source tags/pairs, immutable metadata and invalid numeric inputs.

Use uv/hatchling with locked dev tools; run pytest, strict mypy, ruff, wheel build and clean-wheel smoke on Python 3.11. Commit/merge/push feature/quantity-primitives only after checks. No device, serial, model, firmware or fan operations.

TODO for the remaining M0: units/errors/logging helpers, import-direction guard and CI. Future scientific functions must implement and verify their own uncertainty equations; this type does not invent uncertainties or implement the instrument. Planned CLI/simulator/hardware milestones remain unimplemented.
