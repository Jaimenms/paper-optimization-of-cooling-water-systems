# tools

* `parse_gams_lst.py` — parses the `Display` blocks of the original GAMS listing files
  (`docs/raw/Fonte/Desenv4/*.lst`) into JSON. The extracted values, used as reference during
  the port, are stored in `tests/reference/d4_*.json`:

  ```bash
  .venv/bin/python tools/parse_gams_lst.py docs/raw/Fonte/Desenv4/coolingnetwork_applied_v21_part3.lst tests/reference/d4_part3.json
  ```

  `part2_initial` / `part2_actual` → Table 8, `part2_actual_simulation` → desired flow rates of
  Table 12, `part3` → Table 10, `part3_quad_dif` → purely hydraulic run (unlimited budget variant),
  `part4_case01_redo` → three points of the budget sweep.
