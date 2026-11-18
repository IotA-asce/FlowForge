"""Static enforcement of ADR-0002; fixtures never execute package modules."""

import ast
from pathlib import Path

import pytest

# Bottom to top, matching architecture.md §4.2. Quantity belongs with the leaves.
TIERS = (
    {"units", "provenance", "quantity", "errors", "logging"},
    {"devices"},
    {"acquisition"},
    {"calibration"},
    {"storage"},
    {"experiments"},
    {"signal"},
    {"aero"},
    {"analysis"},
    {"report"},
    {"cli", "dashboard"},
)
SCIENTIFIC = {"signal", "aero", "analysis", "report"}


def layer(module: str) -> str:
    if module == "flowforge":
        return "quantity"  # Public facade may only re-export leaf utilities.
    name = module.split(".")[1]
    if not any(name in tier for tier in TIERS):
        raise ValueError(f"unclassified module: {module}")
    return name


def rank(module: str) -> int:
    return next(i for i, tier in enumerate(TIERS) if layer(module) in tier)


def violations(sources: dict[str, str], packages: set[str]) -> list[str]:
    graph: dict[str, set[str]] = {module: set() for module in sources}
    errors: list[str] = []
    for module, source in sources.items():
        rank(module)  # New top-level modules must be deliberately classified.
        package = module if module in packages else module.rpartition(".")[0]
        for node in ast.walk(ast.parse(source)):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    parts = package.split(".")
                    if node.level > len(parts):
                        raise ValueError(f"relative import escapes package: {module}")
                    base = ".".join(parts[: len(parts) - node.level + 1] + ([base] if base else []))
                targets = [base]
                targets.extend(
                    f"{base}.{alias.name}"
                    for alias in node.names
                    if f"{base}.{alias.name}" in sources
                )
            elif isinstance(node, ast.Call):
                # Keep internal dependencies statically inspectable. This is a
                # developer guard, not a sandbox against disguised Python code.
                function = node.func
                if (isinstance(function, ast.Name) and function.id == "__import__") or (
                    isinstance(function, ast.Attribute) and function.attr == "import_module"
                ):
                    errors.append(f"{module}:{node.lineno}: dynamic import requires review")
            for target in targets:
                if target != "flowforge" and not target.startswith("flowforge."):
                    continue
                graph[module].add(target)
                if rank(target) > rank(module):
                    errors.append(f"{module}:{node.lineno}: upward import of {target}")

    for module in sources:
        if layer(module) not in SCIENTIFIC:
            continue
        pending = list(graph[module])
        visited: set[str] = set()
        while pending:
            target = pending.pop()
            if target in visited:
                continue
            visited.add(target)
            if layer(target) == "devices":
                errors.append(f"{module}: device dependency through {target}")
            pending.extend(graph.get(target, set()))
    return errors


def test_source_import_direction() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "flowforge"
    sources: dict[str, str] = {}
    packages: set[str] = set()
    for path in root.rglob("*.py"):
        parts = ("flowforge", *path.relative_to(root).with_suffix("").parts)
        module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        sources[module] = path.read_text(encoding="utf-8")
        if path.name == "__init__.py":
            packages.add(module)
    assert sources, "no package source was inspected"
    assert not (errors := violations(sources, packages)), "\n".join(errors)


@pytest.mark.parametrize(
    "source,packages,module",
    [
        ("import flowforge.cli", set(), "flowforge.quantity"),
        ("from flowforge.cli import main", set(), "flowforge.quantity"),
        ("from .cli import main", set(), "flowforge.quantity"),
        ("from ..cli import main", set(), "flowforge.devices.serial"),
        ("from ..cli import main", {"flowforge.devices"}, "flowforge.devices"),
        ("from . import cli", {"flowforge"}, "flowforge"),
        ("from flowforge import cli", set(), "flowforge.quantity"),
        ("if False:\n import flowforge.cli", set(), "flowforge.quantity"),
    ],
)
def test_upward_imports_are_rejected(source: str, packages: set[str], module: str) -> None:
    assert any(
        "upward import" in error
        for error in violations({module: source, "flowforge.cli": ""}, packages)
    )


def test_downward_peer_and_external_imports_are_allowed() -> None:
    assert (
        violations(
            {
                "flowforge.cli": "from flowforge.quantity import Quantity\nimport json",
                "flowforge.quantity": "from .provenance import Provenance",
                "flowforge.provenance": "from enum import StrEnum",
            },
            set(),
        )
        == []
    )


@pytest.mark.parametrize("source", ["", "import flowforge.unknown"])
def test_unknown_layers_require_classification(source: str) -> None:
    with pytest.raises(ValueError, match="unclassified"):
        violations({"flowforge.unknown" if not source else "flowforge.cli": source}, set())


def test_relative_import_cannot_escape_package() -> None:
    with pytest.raises(ValueError, match="escapes package"):
        violations({"flowforge.quantity": "from .. import outside"}, set())


@pytest.mark.parametrize("source", ["__import__('flowforge.cli')", "importlib.import_module('x')"])
def test_dynamic_import_calls_require_review(source: str) -> None:
    assert any(
        "dynamic import" in error for error in violations({"flowforge.quantity": source}, set())
    )


def test_scientific_layers_cannot_reach_devices_even_indirectly() -> None:
    errors = violations(
        {
            "flowforge.aero": "from flowforge.calibration import fit",
            "flowforge.calibration": "import flowforge.devices",
            "flowforge.devices": "",
        },
        set(),
    )
    assert any("device dependency" in error for error in errors)
