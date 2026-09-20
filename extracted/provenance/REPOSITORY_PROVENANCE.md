# Repository provenance used for the scratch build

The scratch architecture was reconstructed after inspecting the attached repositories. Concepts and interfaces were drawn from these source locations:

- `remix-12th-sept-dhappa-v4.6-regime-aware(3).zip`
  - `src/utils/unifiedWalkForwardEngine.ts`
  - `src/utils/engineSynergyEngine.ts`
  - `src/utils/drawRegimeEngine.ts`
  - `src/utils/gSquareMethodEngine.ts`
  - `src/utils/gSquareHarmonicsEngine.ts`
  - `src/utils/harufPyramidEngine.ts`
  - `src/utils/modelFEngine.ts`
  - `src/utils/sirAbhishekTheoryEngine.ts`
  - `src/utils/dateIntelligenceEngine.ts`
- `supreme-kai-dhappa(1).zip`
  - `src/utils/freezeSnapshotStore.ts`
  - `src/utils/integrityRegimeEngine.ts`
  - `src/utils/engineSelfLearningCalibrator.ts`
  - `src/utils/mlLearnedRulesEngine.ts`
- `remix-date-pair-generator-&-risk-reward-simulator(4).zip`
  - `Merged_Workbook.csv` used as the packaged historical data source.
  - Date-generator / square / family concept implementations under `src/utils/`.
- `dhappa-v4.6-conformity-purge-phase3(2).zip`
  - conformity reports and utilities were reviewed for integrity concerns and duplicated layers.
- `pip-main (2).zip` and `remix-dhappa-v.2(4).zip`
  - compared for duplicated engine utilities and historical implementation drift.

## Important implementation note

The delivered `dhappa/model.py` is a clean research core, not a verbatim concatenation of the original TypeScript applications. Engine concepts were reconstructed behind a common adapter contract so that the temporal kernel, election logic, freeze hashes, and audit outputs are centralized and testable.
