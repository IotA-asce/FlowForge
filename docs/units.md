# Units at config and display edges

`flowforge.units` implements the accepted M0 leaf utilities. Internal values are
SI; call these explicit scalar functions only when parsing config or displaying
values (architecture section 11).

| Function pair | Forward relation | Reverse relation |
| --- | --- | --- |
| `mm_to_m`, `m_to_mm` | mm / 1000 | m × 1000 |
| `g_to_kg`, `kg_to_g` | g / 1000 | kg × 1000 |
| `percent_to_fraction`, `fraction_to_percent` | percent / 100 | fraction × 100 |
| `celsius_to_kelvin`, `kelvin_to_celsius` | °C + 273.15 | K − 273.15 |

All functions accept finite Python floats or integers and return floats. Booleans
and other types raise TypeError; nonfinite or unrepresentable input and overflowing
results raise ValueError. Absolute temperatures below −273.15 °C or 0 K are
rejected; absolute zero is allowed. Signed linear differences remain valid.
Percent helpers do not impose a 0–100 range: a channel such as relative humidity
must validate its own physical/configuration limits later.

For example, `mm_to_m(25)` gives 0.025 m and `celsius_to_kelvin(20)` gives
293.15 K. These are conversion fixtures, not measured results. Use Quantity
with explicit uncertainty/provenance when reporting measurements.

The temperature helpers convert absolute values, **not temperature differences
or uncertainties**. They do not accept/convert Quantity, infer uncertainty,
change provenance, parse unit strings, or enforce dimensional arithmetic. A
Celsius uncertainty must never have 273.15 added to it. Binary floating-point
rounding/underflow still apply; tests use documented approximate tolerances and
are not a calibrated physical-accuracy claim. Quantity's existing unit field
remains a reporting label.

Errors/logging helpers remain M0 TODOs. No instrument CLI, config parser,
simulator, hardware or physical validation is implemented by these functions.
