# cases/

Input data of the case studies, fully editable (YAML validated by the pydantic schema in
`src/coolingnet/config/schema.py`).

| File | Content |
|---|---|
| `paper_case.yaml` | the example of Souza, Levy & Costa (2018), Section 3.1: network of Fig. 1, Tables 1-7 and the scenario definitions of Sections 3.2-3.7 |
| `example_six_coolers.yaml` | the paper network with a sixth cooler (E-106) and a few changed parameters, written by notebook `07_custom_network` |

`paper_case.yaml` is a copy of the file packaged with the library,
`src/coolingnet/data/paper_case.yaml`, which is what `load_case()` (no argument), the notebooks
and the CLI use by default. The packaged file is the reference that reproduces the published
tables; edit the copy here (or export another one with `coolingnet export-config my_case.yaml`)
and pass it explicitly:

```bash
uv run coolingnet validate cases/my_case.yaml          # schema, catalogues, topology, circuits
uv run coolingnet run cases/my_case.yaml --out results_my_case
uv run coolingnet figures cases/my_case.yaml --results results_my_case --out figures_my_case
```

Both files must stay identical (`tests/test_reference_data.py` checks it); the notebook `00`
writes an additional plain export to `cases/my_case.yaml` (ignored by git).
