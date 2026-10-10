# data/reference/

Reference values used by the tests, the notebooks and `coolingnet eval`.

| File | Content | Source |
|---|---|---|
| `published_values.json` | Tables 8-12, the values printed in Figs. 9-10, the designs of Figs. 2-3, 5-6 and 11 and the numbers quoted in the text of Sections 3.3-3.7 | the paper (units as printed) |
| `d4_part2_initial.json` | existing network, initial condition (Table 8) | `legacy/gams/..._part2_initial.lst` |
| `d4_part2_actual.json` | existing network, current condition (Table 8, Section 3.2) | `legacy/gams/..._part2_actual.lst` |
| `d4_part2_actual_simulation.json` | desired cooling water flow rates (Table 12, Section 3.7) | `legacy/gams/..._part2_actual_simulation.lst` |
| `d4_part3.json` | unlimited budget, Cases 1 and 2 (Table 10) | `legacy/gams/..._part3.lst` |
| `d4_part3_quad_dif.json` | purely hydraulic objective, unlimited budget variant (not in the paper) | `legacy/gams/..._part3_quad_dif.lst` |
| `d4_part4_case01_redo.json` | one point of the budget sweep, B = 2437.5 USD/y (Figs. 7-8) | `legacy/gams/..._part4_case01_redo.lst` |

The `d4_*.json` files are the `Display` blocks of the GAMS listings parsed by
`scripts/parse_gams_lst.py` (`{group: {"title", "symbols": {...}}}`, `.L` levels under the bare
symbol name). `published_values.json` is loaded by `coolingnet.reporting.paper_reference`
(`TABLE8`, `TABLE9`, ... as pandas frames).
