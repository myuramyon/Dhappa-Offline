# DHAPPA Dynamic Primary Engine — Scratch Build v2.0

Clean research implementation reconstructed from the attached DHAPPA repositories. V2 upgrades only the election/routing layer while preserving candidate generators, so election changes remain measurable.

## Run bounded validation

```bash
python run.py
```

## Integrity test

```bash
python test_integrity.py
```

## Full-history research run

```bash
python run_full.py
```

The full-history run is compute-heavy because eligible pair/triplet combinations are frozen and evaluated prospectively.

## V2 election controls

- House-specific champion/challenger gating
- 15/30/60/expanding multi-window agreement
- Minimum-tenure hysteresis
- Qualified combination survival test
- Bounded contextual regime routing
- Explicit `NO_QUALIFIED_PRIMARY` abstention state
- Outcome profiles updated only after election/freeze

## Temporal invariant

For each target row treated as `t-1`, engines receive only historical rows through the immediately preceding row (`t-2`). Rankings and election are frozen before the target result is evaluated.

This is a research backtest framework; evidence labels and ranking metrics are not guaranteed probabilities.

## v2.1 — Champion Protection & Challenger Proof

v2.1 is an experimental election branch. A score-leading challenger can replace a surviving incumbent only after prior-only paired comparison on the same historical target dates. The proof records mean rank delta, rank wins/losses/ties, Top-5 rescues, Top-5 damaged hits, net Top-5, net Top-10, MRR delta, exact sign-test evidence, and 15/30/60 persistence.

Important: v2.1 materially reduces switching but does not uniformly improve predictive metrics. See `reports/DHAPPA_V2_V2_1_COMPARISON.md`. It should not automatically replace v2.0 as canonical until the protection rule is made asymmetric for strong versus weak incumbents.

## v2.2 — Asymmetric Champion Protection

v2.2 makes incumbent protection strength-dependent instead of universal:

- `STRONG`: full paired proof + 7-target tenure + non-negative Top-5 damage budget.
- `MODERATE`: reduced margin and 5-target tenure with positive paired rank evidence.
- `WEAK`: fast 3-target replacement path; challenger must avoid net Top-5 damage.
- `FAILING`: incumbent is not force-protected; a qualified challenger may replace after 2 targets, otherwise the system can abstain with `NO_QUALIFIED_PRIMARY`.

The bounded 240-row replay shows recovery versus v2.1 in DS, GB and GL Top-5, but degradation in FB. Therefore v2.2 is a research improvement to the lock-in mechanism, not a universally calibrated final election policy. See `reports/DHAPPA_V2_1_V2_2_COMPARISON.md`.

## Dynamic Election v2.3 — House-Specific Policy Learning

`run_v2_3.py` adds a prior-only house-specific switch-policy calibrator. Each house independently selects among CONSERVATIVE, BALANCED, ADAPTIVE, and FAST_RESCUE from completed historical challenger events. Calibration never uses the current target before election freeze.

The switch utility jointly considers Top-5 rescue, Top-10 quality, reciprocal-rank / rank improvement, damaged incumbent Top-5 hits, and switching cost. If challenger-event history is insufficient, the system falls back to BALANCED rather than inventing a house rule.

Artifacts include `house_policy_history_v2_3.json`, `house_policy_calibration_events_v2_3.json`, the v2.3 backtest report, and a v2.2-v2.3 comparison. v2.3 is intentionally treated as a research branch because improvement is not uniform across houses.


## v2.5 — Pareto Policy Survival + Incumbent Baseline
Candidate election policies are now shadow-tested against BALANCED, current incumbent policy, and recent surviving policy. If no candidate Pareto-survives protected Top-5/Top-10/MRR/damage constraints, the system retains the current policy instead of forcing a policy change. Run `python run_v2_5.py` and `python test_integrity_v2_5.py`.


## v2.6 — Route-Level Counterfactual Election Lab

V2.6 adds a diagnostic-only counterfactual replay over the frozen v2.5 election system. For every historical target it records the selected route rank, best already-qualified alternative, best single engine, best tested combination, and best generated route after outcome reveal. It classifies misses into ELECTION_MISS, QUALIFICATION_MISS, GENERATION_MISS, RANKING_DEPTH_MISS, ABSTENTION_OPPORTUNITY_COST, and CORRECT_PROTECTION. Oracle-best identities are never fed into the same-target election. Run `python run_v2_6.py`.

## v2.7 — Prospective Route Discriminator

v2.7 adds an online, prior-only route discriminator over already-qualified routes. It is **not allowed to control election by default**. It must first outperform the canonical v2.5 route scorer in completed shadow decisions on both expanding and recent-30 windows, with positive Top-5 rescue, non-negative Top-10 delta, and positive MRR delta. Same-target labels are appended only after election freeze/outcome reveal.

Run: `python run_v2_7.py`
Integrity: `python test_integrity_v2_7.py`


## v2.8 Qualification Boundary Rescue Lab
Adds QUALIFIED / NEAR_QUALIFIED_CHALLENGER / REJECTED bands, strict paired rescue proof, prior-only shadow survival, damage-bounded admission, and audit artifacts. Boundary admissions do not override election gates automatically.

## v2.9 — Post-Admission Challenger Tournament

Admitted boundary routes no longer re-enter the ordinary route-score hierarchy. They receive a dedicated prior-only paired tournament versus the frozen canonical Primary. Outcomes are `BOUNDARY_CHALLENGER_WINS_TOURNAMENT`, `CANONICAL_PRIMARY_RETAINED`, or `NO_DECISION_RETAIN_PRIMARY`. A challenger must show positive net Top-5 rescue, bounded Top-5 damage, non-negative Top-10/MRR, rank improvement, persistence, and independent route evidence. The current target outcome is never used to decide the tournament.


## v3.0 — Candidate-Level Cross-Route Fusion Intelligence
Run `python run_v3_0.py`. Candidate fusion stays in shadow/probation until prior-only evidence proves sustained benefit; otherwise v2.9 canonical output is retained.

## v3.1 Candidate Evidence Attribution & Rank-6–12 Rescue

`run_v3_1.py` adds a leakage-safe Top-5 rescue overlay. It attributes evidence to canonical ranks 1–12 using prior-qualified route agreement, weighted reciprocal rank, route reliability, and family diversity. A Rank 6–12 challenger can swap with the weakest Top-5 incumbent only after shadow evidence and prospective probation pass. Current-target outcomes are appended only after the proposal is frozen.

## v3.2 — Contextual Rescue Attribution Lab
Adds hierarchical pre-target context survival on top of v3.1 Rank-6–12 rescue. Contexts use only information available before the target outcome (house, weekday/gap regime, primary route, challenger rank band, incumbent rank, support/diversity bins, margin bin, incumbent strength). Same-target outcomes are appended only after the rescue decision is frozen.

## v3.3 — Miss-Cause Learning at Candidate Level
Run `python run_v3_3.py` after the v3.2 research artifacts are present. It creates a post-reveal miss-cause audit and a strictly prior-only causal-signature correction shadow replay. Diagnostic outcome labels never modify the same target.


## v3.4 — Error-Specific Ranking Weight Calibration

Run `python run_v3_4.py`. v3.4 calibrates separate prior-only correction families for route bias, vote distortion, redundancy, reliability weighting and rank-anchor bias. Each family must pass SHADOW → PROBATION → LIVE before it may alter Rank 6–12 vs Top-5 ordering.

## v3.5 — Activation Precision Controller

`run_v3_5.py` adds a high-precision intervention controller on top of v3.4. It requires multi-family agreement, near-boundary rank, strong reliability advantage, weak incumbent evidence and minimum challenger diversity. The controller can only suppress a v3.4 correction; it never creates a new candidate. A rolling prior-only circuit breaker disables intervention after evidence of damage.


## v3.6 — Rank-5 Vulnerability Model

v3.6 adds a suppressive vulnerability controller above v3.5. A v3.5-approved correction may intervene only when the displaced candidate is the true canonical Rank-5 candidate and its frozen pre-target evidence is HIGH vulnerability: low Top-10 support, low family diversity, low reliability-weighted support, primary-only dependence and low incumbent evidence score, with independent challenger confirmation. The controller cannot create new candidates or activate a correction that v3.5 rejected. See `run_v3_6.py` and `reports/DHAPPA_RANK5_VULNERABILITY_V3_6_REPORT.md`.


## v3.7 Rank-5 False-Positive Survival Model
Run `python run_v3_7.py`. This layer is suppressive over v3.6 and uses hierarchical prior-only survival cohorts. See `reports/DHAPPA_RANK5_FALSE_POSITIVE_SURVIVAL_V3_7_REPORT.md`.

## v3.8 — Rank-5 Boundary Dataset Expansion + Out-of-Sample Replay

v3.8 expands boundary learning from intervention-triggered cases to every elected historical target. For each target it freezes three comparisons: canonical Rank-5 versus Rank-6, Rank-7 and Rank-8. Pre-target evidence includes individual-engine support, family diversity, prior-only reliability-weighted reciprocal rank, and structural boundary features. Outcome labels (RESCUE/DAMAGE/NEUTRAL) are appended only after reveal.

Artifacts:
- `reports/rank5_boundary_expanded_dataset_v3_8.json`
- `reports/rank5_boundary_dataset_summary_v3_8.json`
- `reports/rank5_boundary_oos_replay_v3_8.json`
- `reports/dynamic_primary_engine_backtest_v3_8.json`
- `reports/rank5_boundary_integrity_v3_8.json`
- `reports/DHAPPA_RANK5_BOUNDARY_EXPANSION_V3_8_REPORT.md`
- `reports/DHAPPA_V3_7_V3_8_COMPARISON.md`


## v3.9 — Challenger Identity & Transition Intelligence
Run `python run_v3_9.py`. Builds a candidate-specific Rank-6/7/8 tournament using digit structure, recency/gap, palti/mirror, previous-draw transition, cross-house recurrence and engine-support composition. Rank-5 vulnerability remains a separate admission gate.


## v4.0 — Full Candidate Learning-to-Rank
Run `python run_v4_0.py`. Ranks all 00–99 candidates using strictly pre-target engine/rank/reliability/structure/recency/transition features. Online model updates happen only after reveal; live promotion requires shadow + prospective probation survival.


## v4.0 — Full Candidate Learning-to-Rank
Run `python run_v4_0.py`. Ranks all 00–99 candidates using strictly pre-target engine/rank/reliability/structure/recency/transition features. Online model updates happen only after reveal; live promotion requires shadow + prospective probation survival.


## v4.0 — Full Candidate Learning-to-Rank
Run `python run_v4_0.py`. Ranks all 00–99 candidates using strictly pre-target engine/rank/reliability/structure/recency/transition features. Online model updates happen only after reveal; live promotion requires shadow + prospective probation survival.

## v4.1 — Learning-to-Rank Feature Ablation & Signal Audit
Run `python run_v4_1.py`. It trains FULL plus nine leave-one-feature-family-out online rankers under the same chronological protocol. NO_QUALIFIED_PRIMARY dates are excluded from canonical rank comparisons. Feature-family conclusions require direction consistency across chronological discovery and confirmation segments; no ablation variant is automatically promoted.


## v4.2 — House-Specific Feature Policy with Nested Prospective Validation
Run `python run_v4_2.py`. Selects each house feature policy only inside an earlier nested discovery segment, freezes the choice, then tests it on an untouched later confirmation segment. Promotion requires higher Top-5 with non-inferior Top-10 and MRR.


## v4.3 — Pairwise Candidate Ordering / Top-5 Objective Ranker
Run `python run_v4_3.py`. Trains an online pairwise ranker after each target reveal, emphasizing canonical ranks 4–8 as hard negatives. Shadow/probation/live survival gates prevent same-history improvement from becoming automatic production promotion.
