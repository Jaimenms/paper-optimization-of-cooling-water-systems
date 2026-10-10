"""NLP-based branch-and-bound for the debottlenecking MINLP (an SBB-like algorithm).

The paper solved the problem with GAMS/SBB: a branch-and-bound whose nodes are NLP
relaxations solved by a local solver (CONOPT). This module implements the same idea
in Python with IPOPT (through CasADi) as node solver:

* the Pyomo model is translated once; nodes only change variable bounds;
* branching is done on the one-hot selection groups (`y_pi[p, :]`, `y_pu[u, :]`) with
  SOS1-style dichotomies over the ordered catalogue, which keeps the tree shallow;
* best-bound node selection, `optcr`/`optca` style termination, time and node limits;
* a failed node NLP is retried from the root point and then fathomed (as SBB does).

Because the NLPs are non-convex, node values are not rigorous lower bounds: like SBB,
the method returns a high-quality local optimum, not a global certificate.
"""

from __future__ import annotations

import heapq
import itertools
import logging
import math
import time
from dataclasses import dataclass, field

import numpy as np
import pyomo.environ as pyo

from coolingnet.optimization.casadi_bridge import IPOPT_DEFAULTS, CasadiProblem, translate

try:
    import casadi as ca
except ImportError:  # pragma: no cover
    ca = None

log = logging.getLogger(__name__)


@dataclass(order=True)
class _Node:
    bound: float
    seq: int
    lbx: np.ndarray = field(compare=False)
    ubx: np.ndarray = field(compare=False)
    x0: np.ndarray = field(compare=False)
    depth: int = field(compare=False, default=0)


@dataclass
class BBResult:
    status: str  # optimal | feasible | infeasible | error
    objective: float | None
    bound: float | None
    x: np.ndarray | None
    nodes: int
    nlps: int
    time_s: float
    message: str = ""


class NlpBranchAndBound:
    def __init__(
        self,
        model: pyo.ConcreteModel,
        *,
        rel_gap: float = 1e-3,
        abs_gap: float = 1e-3,
        time_limit_s: float = 900.0,
        node_limit: int = 20000,
        max_node_iter: int = 1000,
        integrality_tol: float = 1e-5,
        feasibility_tol: float = 1e-6,
        verbose: bool = False,
        cutoff: float | None = None,
        ipopt_options: dict | None = None,
        multistart: int = 4,
        local_search_steps: int = 1,
        seed: int = 12345,
    ):
        if ca is None:  # pragma: no cover
            raise RuntimeError("casadi is required for the NLP branch-and-bound")
        self.model = model
        self.prob: CasadiProblem = translate(model)
        self.rel_gap, self.abs_gap = rel_gap, abs_gap
        self.time_limit_s, self.node_limit = time_limit_s, node_limit
        self.integrality_tol, self.feasibility_tol = integrality_tol, feasibility_tol
        self.verbose = verbose
        self.cutoff = cutoff
        opts = {**IPOPT_DEFAULTS, "print_level": 0, "max_iter": max_node_iter}
        opts.update(ipopt_options or {})
        self.solver = ca.nlpsol(
            "node",
            "ipopt",
            {"x": self.prob.x, "f": self.prob.f, "g": self.prob.g},
            {"ipopt": opts, "print_time": False, "error_on_fail": False},
        )
        self.g_fun = ca.Function("g", [self.prob.x], [self.prob.g])
        self.f_fun = ca.Function("f", [self.prob.x], [self.prob.f])
        self.lbg, self.ubg = np.array(self.prob.lbg), np.array(self.prob.ubg)
        self.discrete = np.array(self.prob.discrete, dtype=bool)
        self.groups = self._selection_groups()
        self.valve_idx = [
            i
            for i, v in enumerate(self.prob.variables)
            if v.parent_component().local_name.endswith("lvalve")
        ]
        self.multistart = multistart
        self.local_search_steps = local_search_steps
        self.rng = np.random.default_rng(seed)
        self.nlps = 0
        self.root_x: np.ndarray | None = None

    # ------------------------------------------------------------------ helpers
    def _selection_groups(self) -> list[list[int]]:
        """Indices of the one-hot groups (same Pyomo component, same leading indices)."""
        groups: dict[tuple, list[int]] = {}
        singles: list[list[int]] = []
        for i, v in enumerate(self.prob.variables):
            if not self.discrete[i]:
                continue
            parent = v.parent_component()
            idx = v.index()
            if isinstance(idx, tuple) and len(idx) >= 2:
                groups.setdefault((parent.name, idx[:-1]), []).append(i)
            else:
                singles.append([i])
        return [g for g in groups.values()] + singles

    def _solve_nlp(self, lbx, ubx, x0):
        self.nlps += 1
        res = self.solver(x0=x0, lbx=lbx, ubx=ubx, lbg=self.lbg, ubg=self.ubg)
        stats = self.solver.stats()
        x = np.asarray(res["x"]).ravel()
        g = np.asarray(self.g_fun(x)).ravel()
        viol = float(np.max(np.maximum(self.lbg - g, 0.0).max(initial=0.0) if g.size else 0.0))
        viol = max(viol, float(np.maximum(g - self.ubg, 0.0).max(initial=0.0)) if g.size else 0.0)
        viol = max(
            viol,
            float(np.maximum(lbx - x, 0.0).max(initial=0.0)),
            float(np.maximum(x - ubx, 0.0).max(initial=0.0)),
        )
        ok = bool(stats.get("success")) or (
            str(stats.get("return_status")) in ("Solved_To_Acceptable_Level",)
        )
        return (
            ok and viol <= self.feasibility_tol,
            float(res["f"]),
            x,
            str(stats.get("return_status")),
        )

    def _is_integral(self, x) -> bool:
        return bool(
            np.all(np.abs(x[self.discrete] - np.round(x[self.discrete])) <= self.integrality_tol)
        )

    def _pick_group(self, x) -> tuple[list[int], int] | None:
        """Most fractional one-hot group and the SOS1 split position."""
        best, best_score = None, 0.0
        for g in self.groups:
            vals = x[g]
            frac = np.minimum(vals, 1.0 - vals)
            score = float(frac.sum())
            if score > best_score + 1e-9:
                best, best_score = g, score
        if best is None or best_score <= self.integrality_tol:
            return None
        vals = np.clip(x[best], 0.0, None)
        if vals.sum() <= 0:
            split = len(best) // 2
        else:
            center = float(np.dot(np.arange(len(best)), vals) / vals.sum())
            split = int(math.floor(center)) + 1
            split = min(max(split, 1), len(best) - 1)
        return best, split

    def _valve_starts(self, x, ub) -> list[np.ndarray]:
        """Starting points for the fixed-design NLP: given point, open valves, random throttling."""
        starts = [x]
        if self.root_x is not None:
            starts.append(self.root_x)
        if self.valve_idx:
            cap = np.array([min(ub[i] if np.isfinite(ub[i]) else 1.0, 1.0) for i in self.valve_idx])
            x_open = x.copy()
            x_open[self.valve_idx] = 0.0
            starts.append(x_open)
            for _ in range(max(self.multistart - 1, 0)):
                xr = x.copy()
                xr[self.valve_idx] = self.rng.uniform(0.0, 0.5, size=len(self.valve_idx)) * cap
                starts.append(xr)
        return starts

    def _polish(self, x, lbx, ubx, assignment: np.ndarray | None = None):
        """Fix the binaries (rounded `x`, or `assignment`) and solve the NLP from several starts."""
        lb, ub = lbx.copy(), ubx.copy()
        r = np.round(x[self.discrete]) if assignment is None else assignment
        lb[self.discrete] = r
        ub[self.discrete] = r
        best = (False, math.inf, None, "not solved")
        for start in self._valve_starts(x, ub):
            ok, f, xp, status = self._solve_nlp(lb, ub, start)
            if ok and f < best[1]:
                best = (ok, f, xp, status)
        return best

    def solve_fixed(self) -> BBResult:
        """No free binaries: multi-start NLP (used for simulations and valve-only problems)."""
        t0 = time.perf_counter()
        lbx0, ubx0 = np.array(self.prob.lbx, dtype=float), np.array(self.prob.ubx, dtype=float)
        x0 = np.array(self.prob.x0, dtype=float)
        ok, f, x, status = self._polish(x0, lbx0, ubx0, assignment=np.round(x0[self.discrete]))
        if not ok:
            return BBResult(
                "infeasible",
                None,
                None,
                None,
                0,
                self.nlps,
                time.perf_counter() - t0,
                f"NLP failed: {status}",
            )
        return BBResult(
            "optimal",
            f,
            f,
            x,
            0,
            self.nlps,
            time.perf_counter() - t0,
            f"multi-start NLP ({self.nlps} solves)",
        )

    # ------------------------------------------------------------ local search
    def _assignment_of(self, x) -> np.ndarray:
        return np.round(x[self.discrete])

    def local_search(
        self, x: np.ndarray, f: float, lbx, ubx, t_end: float
    ) -> tuple[np.ndarray, float, int]:
        """First-improvement search over neighbouring designs (adjacent catalogue entries)."""
        disc_pos = {i: k for k, i in enumerate(np.flatnonzero(self.discrete))}
        best_x, best_f, moves = x.copy(), f, 0
        improved = True
        passes = 0
        while improved and passes < 6 and time.perf_counter() < t_end:
            improved = False
            passes += 1
            for g in self.groups:
                current = self._assignment_of(best_x)
                sel = [k for k, i in enumerate(g) if current[disc_pos[i]] > 0.5]
                if len(sel) != 1:
                    continue
                k0 = sel[0]
                candidates = [
                    k0 + d
                    for d in range(-self.local_search_steps, self.local_search_steps + 1)
                    if d != 0 and 0 <= k0 + d < len(g)
                ]
                if len(g) <= 6:  # small groups (pump options): try every alternative
                    candidates = [k for k in range(len(g)) if k != k0]
                for k in candidates:
                    if time.perf_counter() > t_end:
                        break
                    if ubx[g[k]] < 0.5:  # excluded by the node bounds
                        continue
                    trial = current.copy()
                    trial[disc_pos[g[k0]]] = 0.0
                    trial[disc_pos[g[k]]] = 1.0
                    ok, ft, xt, _ = self._polish(best_x, lbx, ubx, assignment=trial)
                    if ok and ft < best_f - max(self.abs_gap, 1e-9):
                        best_x, best_f, moves = xt, ft, moves + 1
                        improved = True
                        if self.verbose:
                            log.info("local search: move in group %s -> %.6g", g[0], ft)
                        break
        return best_x, best_f, moves

    # --------------------------------------------------------------------- run
    def run(self) -> BBResult:
        t0 = time.perf_counter()
        lbx0, ubx0 = np.array(self.prob.lbx, dtype=float), np.array(self.prob.ubx, dtype=float)
        x_root = np.array(self.prob.x0, dtype=float)
        incumbent_f = math.inf if self.cutoff is None else float(self.cutoff)
        incumbent_x = None
        seq = itertools.count()

        ok, f, x, status = self._solve_nlp(lbx0, ubx0, x_root)
        if not ok:
            # try from the midpoint of the bounds before giving up
            with np.errstate(invalid="ignore"):
                mid = np.where(np.isfinite(lbx0) & np.isfinite(ubx0), 0.5 * (lbx0 + ubx0), x_root)
            ok, f, x, status = self._solve_nlp(lbx0, ubx0, mid)
        if not ok:
            return BBResult(
                "infeasible",
                None,
                None,
                None,
                1,
                self.nlps,
                time.perf_counter() - t0,
                f"root NLP failed: {status}",
            )
        root_x = x.copy()
        self.root_x = root_x
        heap: list[_Node] = [_Node(f, next(seq), lbx0, ubx0, x, 0)]
        nodes = 0
        best_bound = f
        message = ""
        while heap:
            if time.perf_counter() - t0 > self.time_limit_s:
                message = "time limit"
                break
            if nodes >= self.node_limit:
                message = "node limit"
                break
            node = heapq.heappop(heap)
            best_bound = node.bound
            if incumbent_f < math.inf and node.bound >= incumbent_f - max(
                self.abs_gap, self.rel_gap * abs(incumbent_f)
            ):
                heap.clear()  # best-first: every remaining node is at least as bad
                break
            nodes += 1
            if nodes > 1:
                ok, f, x, status = self._solve_nlp(node.lbx, node.ubx, node.x0)
                if not ok:
                    ok, f, x, status = self._solve_nlp(node.lbx, node.ubx, root_x)
                if not ok:
                    continue  # fathom (SBB behaviour for failed nodes)
                if f >= incumbent_f - max(self.abs_gap, self.rel_gap * abs(incumbent_f)):
                    # non-convex node: confirm the prune from a second starting point
                    ok2, f2, x2, _ = self._solve_nlp(node.lbx, node.ubx, root_x)
                    if ok2 and f2 < f:
                        f, x = f2, x2
                    if f >= incumbent_f - max(self.abs_gap, self.rel_gap * abs(incumbent_f)):
                        continue
            else:
                f, x = node.bound, node.x0
            if self._is_integral(x):
                okp, fp, xp, _ = self._polish(x, node.lbx, node.ubx)
                if okp and fp < incumbent_f:
                    incumbent_f, incumbent_x = fp, xp
                    if self.verbose:
                        log.info(
                            "node %d depth %d: new incumbent %.6g (nlps=%d, open=%d)",
                            nodes,
                            node.depth,
                            fp,
                            self.nlps,
                            len(heap),
                        )
                continue
            pick = self._pick_group(x)
            if pick is None:
                continue
            group, split = pick
            for side in ("low", "high"):
                lb, ub = node.lbx.copy(), node.ubx.copy()
                members = group[split:] if side == "low" else group[:split]
                for i in members:
                    ub[i] = 0.0
                    lb[i] = 0.0
                heapq.heappush(heap, _Node(f, next(seq), lb, ub, x, node.depth + 1))
            if self.verbose and nodes % 25 == 0:
                log.info(
                    "nodes=%d open=%d nlps=%d bound=%.6g incumbent=%.6g",
                    nodes,
                    len(heap),
                    self.nlps,
                    best_bound,
                    incumbent_f,
                )
        # The starting point carries a design (existing network or warm start): always evaluate it,
        # so that the result is never worse than a known feasible design.
        ok0, f0, x0p, _ = self._polish(
            x_root, lbx0, ubx0, assignment=np.round(x_root[self.discrete])
        )
        note = message or "tree exhausted / gap closed"
        if ok0 and f0 < incumbent_f - max(self.abs_gap, 1e-9):
            if incumbent_x is not None:
                note += f"; starting design better than the tree incumbent ({f0:.6g} < {incumbent_f:.6g})"
            else:
                note += "; tree found no integer point, kept the starting design"
            incumbent_f, incumbent_x = f0, x0p
        if incumbent_x is None:
            elapsed = time.perf_counter() - t0
            status = "infeasible" if not message else "error"
            return BBResult(
                status,
                None,
                best_bound,
                None,
                nodes,
                self.nlps,
                elapsed,
                message or "no integer feasible point found",
            )
        if self.local_search_steps > 0:
            f_before = incumbent_f
            incumbent_x, incumbent_f, moves = self.local_search(
                incumbent_x, incumbent_f, lbx0, ubx0, t0 + self.time_limit_s
            )
            if moves:
                note += f"; local search: {moves} improving move(s), {f_before:.6g} -> {incumbent_f:.6g}"
        elapsed = time.perf_counter() - t0
        status = "feasible" if message else "optimal"
        return BBResult(
            status, incumbent_f, best_bound, incumbent_x, nodes, self.nlps, elapsed, note
        )

    def load(self, x: np.ndarray) -> None:
        for v, val, d in zip(self.prob.variables, x, self.discrete, strict=True):
            v.set_value(float(round(val)) if d else float(val), skip_validation=True)
