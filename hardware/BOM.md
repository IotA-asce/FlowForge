# FlowForge V0 — Provisional Bill of Materials

**Status:** provisional. Nothing here has been built or measured yet.

This BOM is written **requirement-first**. Each line states the property that actually matters,
why it matters, and *an* example part that satisfies it. The example parts are illustrative,
not prescriptive — the firmware HAL and the device `hello` descriptor exist precisely so that
substitutions cost one file, not a redesign
([architecture.md §7](../docs/architecture.md#7-firmware-architecture)).

Design point: **100 × 100 mm test section, 4–18 m/s, 25 mm specimens.** Derivation in
[measurement-model.md §2](../docs/measurement-model.md#2-reference-geometry-v0).

Costs are rough 2026 hobbyist retail in USD, for budgeting only.

---

## 1. Airflow

Required volumetric flow: `18 m/s × 0.0100 m² = 0.18 m³/s ≈ 380 CFM` through the test section.

Fans are rated at **free air**. With honeycomb, screens, contraction, and diffuser, expect the
operating point to sit at roughly 60–70 % of free-air flow. Size for ≥50 % margin.

| # | Requirement | Why | Example | Qty | Est. |
| --- | --- | --- | --- | --- | --- |
| 1.1 | 120 mm **high-static-pressure** fan, ≥110 CFM free air, ≥5 mmH₂O max static, **4-pin PWM** with tachometer | Static pressure, not raw airflow, is the binding constraint; the 4-pin PWM input avoids switching fan power and gives a tach for stall detection (SR-11) | Delta AFB1212SHE / Noctua NF-F12 industrialPPC-3000 / Arctic P12 Max | 4 | $60–130 |
| 1.2 | Elastomer fan isolation mounts | Decouples blade-pass vibration from the balance — see [R-02](../docs/technical-risks.md#r-02-fan-vibration-couples-into-the-balance) | silicone anti-vibration fan mounts | 16 | $8 |
| 1.3 | Wire finger guard, 120 mm | Hazard H-1 | standard 120 mm fan guard | 4 | $6 |

Six fans instead of four is a reasonable hedge if the measured fan map falls short of 18 m/s
([R-07](../docs/technical-risks.md#r-07-fan-array-cannot-reach-the-speed-range)).

---

## 2. Tunnel structure

| # | Requirement | Why | Example | Qty | Est. |
| --- | --- | --- | --- | --- | --- |
| 2.1 | **Polycarbonate** sheet, ≥3 mm, for the test section | Impact tolerance if a specimen releases (H-2). **Not acrylic** — acrylic shatters | 3 mm PC sheet, 600 × 400 mm | 1 | $25 |
| 2.2 | Flow straightener: honeycomb, 6–8 mm cell, thickness ≥ 8 × cell diameter (50–60 mm) | Removes swirl and large-scale structure; the L/D ratio is what makes it work | aluminium honeycomb core, or a 3D-printed honeycomb block | 1 | $0–25 |
| 2.3 | Settling screens, 30–40 mesh stainless, 3 layers with ≥30 mm spacing | Breaks down turbulence; placed in the *large* settling chamber where velocity — and hence pressure drop — is low | stainless woven mesh, 250 × 250 mm | 3 | $12 |
| 2.4 | 4 : 1 contraction, 200 × 200 → 100 × 100 mm, smooth (ideally 5th-order polynomial profile) | Reduces axial turbulence intensity roughly in proportion to the contraction ratio | 3D printed in segments, sanded | 1 | filament |
| 2.5 | Diffuser, ≤7° half-angle | Recovers static pressure without separating | 3D printed | 1 | filament |
| 2.6 | Downstream catch screen, coarse | Stops a released specimen before the exhaust (H-2) | 5 mm stainless mesh | 1 | $5 |
| 2.7 | Rigid base / frame, decoupled from the balance stand | The balance must not share structure with the fans | 2020 aluminium extrusion + brackets, or 18 mm ply | 1 set | $30 |
| 2.8 | Fasteners, gasket foam, sealing tape | Leaks upstream of the test section corrupt the airspeed reference | assorted M3/M4, EPDM tape | 1 set | $15 |

Total printed volume for tunnel parts: roughly 1.5–2 kg of PLA or PETG. PETG is preferred for
the contraction and diffuser (less prone to creep near warm fans).

---

## 3. Force balance

The most precision-sensitive subassembly. Topology and rationale in
[measurement-model.md §5.1](../docs/measurement-model.md#51-balance-topology).

| # | Requirement | Why | Example | Qty | Est. |
| --- | --- | --- | --- | --- | --- |
| 3.1 | Strain-gauge load cell, **100 g** (alternate 300 g), ≤0.05 % FS non-linearity, ≤0.05 % FS hysteresis | Working range at the cell is ~0–15 gf after the 3:1 lever; a 5 kg cell would put the whole signal in its bottom 0.3 % | TAL221 100 g miniature beam cell | 1 | $12 |
| 3.2 | 24-bit bridge ADC with internal PGA and **sigma-delta** conversion, ≥80 SPS, I²C | Sigma-delta gives inherent anti-alias filtering — see [R-02](../docs/technical-risks.md#r-02-fan-vibration-couples-into-the-balance). Fallback: HX711 (cheaper, noisier, fixed 10/80 SPS) | NAU7802 breakout (SparkFun Qwiic Scale) | 1 | $18 |
| 3.3 | Low-friction pivot: crossed-flexure or miniature ball bearings | Stiction sets the force floor. A flexure has zero stiction and is the better choice if you can make one | 2 × MR63ZZ bearings, or 0.1 mm spring-steel shim flexures | 1 set | $8 |
| 3.4 | Sting: ≤4 mm OD, high stiffness | Support drag scales with frontal area — the dominant systematic ([R-01](../docs/technical-risks.md#r-01-support-drag-dominates-the-measurement)) | 4 mm carbon fibre tube or 3 mm steel rod | 1 | $6 |
| 3.5 | Non-metric sting fairing | Shields the support from the flow without touching the metric side | 3D printed, streamlined section | 1 | filament |
| 3.6 | Mechanical overload stop, ~150 % of cell deflection | Protects the cell from handling (H-7) | printed bracket + M3 grub screws | 1 | — |
| 3.7 | **Shielded twisted-pair** bridge cable, shield grounded at one end | Microvolt signals next to a switching fan supply ([R-05](../docs/technical-risks.md#r-05-electrical-noise-from-fan-pwm)) | 4-core shielded, 0.5 m | 1 | $5 |
| 3.8 | Specimen retention: **M3 screw or threaded stud** | Friction fits become projectiles at 18 m/s (H-2). Non-negotiable | M3 stainless + heat-set inserts | 10 | $6 |
| 3.9 | Keyed/pinned specimen interface | Repeatable orientation between remounts ([R-09](../docs/technical-risks.md#r-09-specimen-mounting-repeatability)) | 2 mm dowel pin + printed socket | 1 | $3 |

---

## 4. Flow sensing

| # | Requirement | Why | Example | Qty | Est. |
| --- | --- | --- | --- | --- | --- |
| 4.1 | Differential pressure sensor, **±500 Pa**, digital I²C, factory-calibrated, ≤0.5 Pa offset, ≤3 % of reading | 18 m/s ⇒ 194 Pa, so ±500 Pa covers the range with headroom; thermal mass-flow types keep useful resolution at the 10 Pa low end where a piezo sensor would not | Sensirion SDP810-500Pa (or SDP31-500Pa) | 1 | $35 |
| 4.2 | Pitot-static probe, ≥3 mm OD, ≥60 mm insertion | Needs both total and static ports; a bare total-pressure tube is not enough | RC/drone stainless pitot-static probe | 1 | $10 |
| 4.3 | Silicone tubing to match probe barbs, ≤300 mm | Long tubing adds lag; short and equal-length on both ports | 2 mm ID silicone, 1 m | 1 | $3 |
| 4.4 | Probe mount with repeatable position and alignment | Probe position error is absorbed into `k`, so it must not change between calibration and use | 3D printed, pinned | 1 | — |

---

## 5. Environmental sensing

| # | Requirement | Why | Example | Qty | Est. |
| --- | --- | --- | --- | --- | --- |
| 5.1 | Combined T / p / RH sensor, I²C, ±1 °C, ±1 hPa, ±3 % RH | Feeds air density and Reynolds number. Note that density **cancels out of `Cd`** ([§6.1](../docs/measurement-model.md#61-air-density-cancels)), so this is the least critical sensor in the system | BME280 breakout | 1 | $8 |
| 5.2 | Mount away from the MCU and regulators, in or near the flow | Self-heating of 1–2 °C is common and biases `Re` | printed standoff + short I²C lead | 1 | — |

---

## 6. Control electronics

| # | Requirement | Why | Example | Qty | Est. |
| --- | --- | --- | --- | --- | --- |
| 6.1 | MCU: dual-core, native USB CDC, ≥2 hardware timers, ≥1 I²C, hardware PWM, hardware watchdog | Deterministic acquisition on one core, comms on the other ([ADR-0003](../docs/adr/0003-firmware-esp32-freertos.md)) | ESP32-S3-DevKitC-1 | 1 | $12 |
| 6.2 | Level shifter / open-drain driver for the fan PWM pin | Intel 4-wire fan spec expects 5 V open-drain at 25 kHz | 74LVC1G07 or a small N-FET per fan | 4 | $4 |
| 6.3 | *Alternative* if 3-pin fans are used: logic-level N-channel MOSFET, ≥5 A, low-side | Switching fan power directly; noisier, and loses tach fidelity | IRLZ44N + gate resistor | 4 | $6 |
| 6.4 | 12 V PSU, ≥5 A, quiet, with a mains inlet | 4 fans at up to 0.6 A each plus margin | 12 V 6 A desktop supply | 1 | $18 |
| 6.5 | Inline fuse holder + 5 A fuse | Hazard H-5 | ATO blade holder | 1 | $4 |
| 6.6 | **Latching NC mushroom E-stop**, ≥12 V DC / 5 A rated | Interrupts fan power independently of the firmware ([safety.md §3](../docs/safety.md#3-the-emergency-stop)) | 22 mm twist-release E-stop | 1 | $10 |
| 6.7 | E-stop sense divider to an MCU GPIO | Lets the firmware *record* the E-stop; it must not be what *actions* it | 2 × resistors | 1 | $1 |
| 6.8 | Star-ground point, separate analogue return | Keeps fan return current out of the bridge ground ([R-05](../docs/technical-risks.md#r-05-electrical-noise-from-fan-pwm)) | terminal block | 1 | $3 |
| 6.9 | Enclosure for mains/PSU and wiring | H-5, H-8 | ABS project box | 1 | $10 |
| 6.10 | USB-C cable, shielded, ≤1 m | Long cables raise CDC error rates | — | 1 | $6 |

---

## 7. Calibration equipment

Without these, no result from this instrument is defensible.

| # | Requirement | Why | Example | Qty | Est. |
| --- | --- | --- | --- | --- | --- |
| 7.1 | Calibration mass set, **OIML M1 or better**, 1 g – 100 g | Directly sets the force scale; its tolerance is a Type B term in every force result | M1 stainless set | 1 | $30 |
| 7.2 | Low-friction pulley, ball-bearing, small diameter | Converts hanging mass into horizontal force at the specimen station ([calibration.md §2](../docs/calibration.md#2-load-cell-force-calibration)); friction here becomes a calibration error | miniature bearing pulley | 1 | $6 |
| 7.3 | Non-stretch thread | Compliance introduces hysteresis | braided Kevlar / Dyneema fishing line | 1 | $4 |
| 7.4 | Digital calipers, 0.01 mm resolution | Reference area is a `Cd` term; measured beats nominal | 150 mm digital calipers | 1 | $20 |
| 7.5 | **Optional but strongly recommended:** reference anemometer (hot-wire or vane) | The only way to calibrate the pitot factor `k`, which enters `Cd` **squared**. Without it `k = 1.0` is `ASSUMED` and every `Cd` becomes `ESTIMATED` | Testo 405i, or a calibrated vane anemometer | 1 | $70–150 |

---

## 8. Safety and consumables

| # | Item | Qty | Est. |
| --- | --- | --- | --- |
| 8.1 | Safety glasses (H-2) | 1 | $8 |
| 8.2 | Hearing protection, if measured level exceeds 80 dBA (H-4) | 1 | $10 |
| 8.3 | PLA and PETG filament | ~2 kg | $40 |
| 8.4 | Heat-set inserts M3, assorted screws | 1 set | $12 |
| 8.5 | Cable ties, strain relief, heat-shrink | 1 set | $8 |
| 8.6 | Sandpaper 240–600 grit, filler primer (specimen finish, [R-10](../docs/technical-risks.md#r-10-surface-finish-and-reynolds-sensitivity)) | 1 set | $12 |

---

## 9. Cost summary

| Group | Low | High |
| --- | --- | --- |
| Airflow | $74 | $144 |
| Tunnel structure | $87 | $112 |
| Force balance | $58 | $70 |
| Flow sensing | $48 | $52 |
| Environmental | $8 | $10 |
| Control electronics | $68 | $82 |
| Calibration (excl. anemometer) | $60 | $70 |
| Safety and consumables | $90 | $100 |
| **Subtotal** | **$493** | **$640** |
| Reference anemometer (optional) | $70 | $150 |

Excludes the 3D printer, hand tools, a multimeter, and an oscilloscope (useful for verifying
the PWM ramp in M8b, not required).

---

## 10. Printed parts list

Sources live in `hardware/cad/`, with editable sources (OpenSCAD or FreeCAD) committed
alongside STL exports.

| Part | Notes |
| --- | --- |
| Fan array plenum | 4 × 120 mm inlet → 200 × 200 mm settling chamber |
| Honeycomb block | if not using aluminium core; ≥8:1 cell L/D |
| Screen frames ×3 | with ≥30 mm spacing |
| Contraction, 4 : 1 | segmented, sanded smooth internally |
| Test-section frame | holds polycarbonate panels, sealed |
| Diffuser | ≤7° half-angle |
| Balance stand | **structurally separate** from the tunnel |
| Pivot housing | flexure or bearing variant |
| Sting fairing | non-metric shroud |
| Specimen mounts | keyed interface, M3 retention |
| Probe mount | repeatable position and alignment |
| Electronics tray | keeps the ADC at the load cell, fan wiring separated |
| Specimens | 25 mm cube, 25 mm sphere, teardrop — identical process parameters |

---

## 11. Open questions

1. **Fan count.** Four is the estimate; the fan map (M9) decides. Reduce the declared speed
   range rather than overdriving the fans.
2. **Flexure vs bearing pivot.** A flexure has no stiction but a finite spring rate that adds
   to the calibration slope — harmless, since the slope is measured end to end. Build both if
   printing is cheap; keep whichever gives lower hysteresis in calibration.
3. **NAU7802 vs HX711.** NAU7802 assumed throughout. If HX711 is used, note the fixed 10/80 SPS
   options and the poorer noise floor, and update the error budget with measured values in M8c.
4. **Honeycomb material.** A printed honeycomb is free but the cell walls are thick relative to
   aluminium core, costing pressure drop. Worth measuring both if the fan margin is tight.
5. **Test-section length.** 300 mm assumed. Longer improves flow development and pressure
   recovery; shorter reduces boundary-layer growth and horizontal buoyancy
   ([R-12](../docs/technical-risks.md#r-12-horizontal-buoyancy)).
