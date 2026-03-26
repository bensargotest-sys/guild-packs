# Guild Feedback Loop — PRD v1.0

> Computed confidence from real-world usage. No human curation. The proof writes itself.

**Date:** 2026-03-26
**Status:** Draft
**Owner:** Hermes Agent

---

## 1. Problem Statement

Guild packs have a feedback loop that's broken in the middle. The system tracks every phase checkpoint and generates feedback YAML — but nothing reads it back. Confidence levels are self-reported by pack authors and never update from actual usage. The adoption_log.jsonl has zero consumers. Feedback files accumulate on disk with no aggregation.

**The result:** A pack applied successfully 50 times still says `confidence: guessed`. A pack that fails 90% of the time looks identical to one that succeeds 90%. Agents can't tell the difference.

**What this PRD fixes:** Close the feedback loop so pack confidence is computed from real outcomes, not publisher claims.

---

## 2. Goals

| Goal | Description |
|------|-------------|
| G1 | Pack confidence computed automatically from apply outcomes |
| G2 | Search ranking influenced by computed confidence |
| G3 | Autosuggest prefers higher-confidence packs |
| G4 | Feedback published automatically (no manual step) |
| G5 | Structured outcome data captured at checkpoint time |

### Non-Goals (explicitly out of scope)

- Cross-organization aggregation (requires network protocol — future)
- Embedding-based semantic search (separate initiative)
- Pack auto-evolution / rewrite (memento-skills territory — future)
- Web dashboard for browsing stats (future)

---

## 3. Architecture

### 3.1 Current State (broken)

```
apply_start → checkpoint (free-text evidence) → complete
                                                    ↓
                                        feedback YAML → disk → END
                                        adoption_log → disk → END
                                                               ↑
                                          nothing reads this ───┘
```

### 3.2 Target State

```
apply_start → checkpoint (structured outcome) → complete
                                                    ↓
                                        feedback YAML → disk
                                        adoption_log → disk
                                                    ↓
                                        confidence_aggregator
                                                    ↓
                                        pack_stats.json (per-pack computed metrics)
                                                    ↓
                                    ┌───────────────┼───────────────┐
                                    ↓               ↓               ↓
                            guild_search      autosuggest     auto-publish
                          (rank by score)   (prefer proven)  (feedback→outbox)
```

### 3.3 Data Flow

```
1. Agent calls guild_apply_checkpoint(session_id, phase, "passed", evidence, outcome={...})
                                                                              ↑
                                                        NEW: structured fields

2. Agent calls guild_apply_complete(session_id, outcome)
   → writes feedback YAML with structured outcome data
   → appends to adoption_log.jsonl
   → calls _aggregate_pack_confidence(pack_id)        ← NEW
   → auto-publishes feedback to outbox                 ← NEW

3. _aggregate_pack_confidence(pack_id):
   → reads all adoption_log entries for this pack_id
   → reads all feedback files for this pack
   → computes: total_applies, pass_rate, unique_contexts, avg_iterations_saved
   → writes to ~/.hermes/guild/pack_stats/{pack_name}.json
   → updates confidence tier

4. guild_search(query):
   → loads pack_stats for each match
   → sorts by computed_score (not self-reported confidence)

5. autosuggest:
   → filters out packs already tried in this session
   → prefers packs with higher computed_score
```

---

## 4. Detailed Design

### 4.1 Structured Outcome Schema

Added to `guild_apply_checkpoint` as an optional `outcome` parameter:

```python
# New parameter on _action_checkpoint
outcome: dict = {
    "resolved": bool,              # did this phase achieve its goal?
    "iterations": int,             # tool calls within this phase
    "error_type": str | None,      # "dependency", "timeout", "wrong_approach", "checkpoint_vague", None
    "context_tags": list[str],     # ["python", "fastapi", "debugging", "async"]
}
```

**Backward compatible:** outcome is optional. Old callers (no outcome dict) still work — the system treats missing outcome as unstructured.

**Evidence remains free-text** — the structured fields supplement it, not replace it.

### 4.2 Adoption Log Schema (enhanced)

Current:
```json
{"ts": "...", "pack_id": "...", "success": true, "phases_passed": 2, "phases_total": 2, "duration_seconds": 0}
```

Enhanced:
```json
{
  "ts": "2026-03-26T12:00:00Z",
  "pack_id": "guild://hermes/systematic-debugging",
  "pack_version": "1.0",
  "session_id": "systematic-debugging-20260326-120000-a1b2c3",
  "success": true,
  "phases_passed": 4,
  "phases_failed": 0,
  "phases_total": 4,
  "duration_seconds": 180,
  "context_tags": ["python", "fastapi", "debugging"],
  "phase_outcomes": [
    {"phase": "investigate", "resolved": true, "iterations": 3, "error_type": null},
    {"phase": "hypothesize", "resolved": true, "iterations": 2, "error_type": null},
    {"phase": "test", "resolved": true, "iterations": 1, "error_type": null},
    {"phase": "implement", "resolved": true, "iterations": 2, "error_type": null}
  ],
  "agent_id": "hermes-agent"
}
```

### 4.3 Pack Stats Schema

Per-pack computed metrics stored at `~/.hermes/guild/pack_stats/{pack_name}.json`:

```json
{
  "pack_id": "guild://hermes/systematic-debugging",
  "pack_name": "systematic-debugging",
  "computed_at": "2026-03-26T12:30:00Z",
  "total_applies": 47,
  "total_passes": 41,
  "total_fails": 6,
  "pass_rate": 0.872,
  "unique_contexts": 12,
  "avg_duration_seconds": 195,
  "avg_phases_passed_ratio": 0.91,
  "phase_pass_rates": {
    "investigate": 0.95,
    "hypothesize": 0.89,
    "test": 0.85,
    "implement": 0.91
  },
  "common_failure_modes": [
    {"error_type": "checkpoint_vague", "count": 3, "phase": "hypothesize"},
    {"error_type": "wrong_approach", "count": 2, "phase": "test"}
  ],
  "context_distribution": {
    "python": 30,
    "javascript": 10,
    "debugging": 25,
    "testing": 8
  },
  "computed_confidence": "tested",
  "computed_score": 0.87
}
```

### 4.4 Confidence Computation Rules

```python
def compute_confidence(stats: dict) -> tuple[str, float]:
    """Returns (confidence_tier, numeric_score)."""
    total = stats["total_applies"]
    pass_rate = stats["pass_rate"]
    contexts = stats["unique_contexts"]

    # Not enough data
    if total < 3:
        return ("guessed", 0.2)

    # Failing more than succeeding
    if pass_rate < 0.5:
        return ("guessed", max(0.1, pass_rate * 0.4))

    # Moderate success, single context
    if total < 10 or contexts < 2:
        if pass_rate >= 0.7:
            return ("inferred", 0.3 + pass_rate * 0.3)
        return ("guessed", 0.2 + pass_rate * 0.2)

    # Good success across multiple contexts
    if pass_rate >= 0.8 and contexts >= 3:
        return ("validated", 0.7 + pass_rate * 0.2 + min(contexts / 20, 0.1))

    if pass_rate >= 0.7:
        return ("tested", 0.5 + pass_rate * 0.3)

    return ("inferred", 0.3 + pass_rate * 0.3)
```

**Score range:** 0.0 to 1.0. Used for search ranking. The tier (guessed/inferred/tested/validated) is derived from the score for display.

**Key principle:** `unique_contexts` is the strongest signal. A pack that works across 10 different problem domains is worth more than one tested 100 times on the same codebase.

### 4.5 Search Ranking

`guild_search` currently returns matches sorted by a basic relevance score (keyword match). Enhanced:

```python
final_score = (keyword_relevance * 0.4) + (computed_score * 0.4) + (recency * 0.2)
```

Where:
- `keyword_relevance`: existing match score (0-1)
- `computed_score`: from pack_stats.json (0-1), defaults to 0.2 if no stats
- `recency`: time decay — full score if updated within 30 days, decays to 0.5 at 90 days

### 4.6 Autosuggest Enhancement

Current: suggests first match from guild_search.

Enhanced:
- Filter out packs in `_tried_packs` set (packs already applied and failed in this session)
- Sort by `computed_score` descending
- Include score in suggestion: "💡 Guild pack: systematic-debugging (87% success across 47 applies)"

### 4.7 Auto-Publish Feedback

Current: agent told "review and publish when ready" — manual step rarely taken.

Enhanced: after `guild_apply_complete`, feedback is automatically saved to outbox:

```python
# In _action_complete, after generating feedback_draft:
_save_to_outbox(feedback_draft, feedback_yaml, feedback_filename)
```

No GitHub PR created automatically (that still needs explicit guild_publish). But the feedback is staged for the next publish batch.

---

## 5. Implementation Plan

### Task 1: Structured Outcome on Checkpoint (0.5 days)

**Files:**
- Modify: `tools/guild_apply.py` — `_action_checkpoint()` accepts optional `outcome` dict
- Modify: `tools/guild_apply.py` — `_log_event()` includes outcome in event
- Test: `tests/tools/test_guild_apply.py` — new tests for outcome parameter

**Success criteria:**
- Checkpoint accepts outcome dict with resolved, iterations, error_type, context_tags
- Outcome stored in phase_results and JSONL log
- Backward compatible — no outcome = works as before

**Verification:**
```bash
pytest tests/tools/test_guild_apply.py -v -k "outcome"
```

### Task 2: Enhanced Adoption Log (0.25 days)

**Files:**
- Modify: `tools/guild_apply.py` — `_action_complete()` writes enhanced adoption_log entry
- Test: `tests/tools/test_guild_apply.py` — verify log schema

**Success criteria:**
- Adoption log entries include session_id, context_tags, phase_outcomes, agent_id
- Old entries still readable (backward compatible read)

**Verification:**
```bash
python -c "import json; [print(json.loads(l).keys()) for l in open('~/.hermes/guild/adoption_log.jsonl')]"
```

### Task 3: Confidence Aggregator (1 day)

**Files:**
- Create: `tools/guild_confidence.py` — `aggregate_pack_confidence(pack_id)`, `compute_confidence(stats)`, `load_pack_stats(pack_name)`, `save_pack_stats(pack_name, stats)`
- Create: `tests/tools/test_guild_confidence.py` — unit tests for all confidence tiers
- Modify: `tools/guild_apply.py` — call aggregator after `_action_complete()`

**Success criteria:**
- Reads adoption_log + feedback files for a pack
- Computes pass_rate, unique_contexts, phase_pass_rates, common_failure_modes
- Writes pack_stats/{pack_name}.json
- Confidence tiers match rules in §4.4

**Verification:**
```bash
pytest tests/tools/test_guild_confidence.py -v
# Manual: apply a pack 3 times, check that pack_stats.json exists and confidence updated
```

### Task 4: Search Ranking by Computed Score (0.25 days)

**Files:**
- Modify: `tools/guild_tools.py` — `guild_search()` loads pack_stats, applies ranking formula
- Test: `tests/tools/test_guild_tools.py` — verify ranking order

**Success criteria:**
- Packs with higher computed_score rank higher
- Packs with no stats default to 0.2 (don't disappear)
- Search results include `computed_confidence` and `computed_score` fields

**Verification:**
```bash
pytest tests/tools/test_guild_tools.py -v -k "search"
```

### Task 5: Autosuggest Enhancement (0.25 days)

**Files:**
- Modify: `tools/guild_autosuggest.py` — use computed_score for ranking, filter tried packs
- Modify: `run_agent.py` — add `_tried_packs` set, populate on failed applies
- Test: `tests/tools/test_guild_autosuggest.py` — verify filtering and ranking

**Success criteria:**
- Autosuggest never re-suggests a pack that already failed in this session
- Higher computed_score packs suggested first
- Suggestion includes score: "87% success across 47 applies"

**Verification:**
```bash
pytest tests/tools/test_guild_autosuggest.py -v
```

### Task 6: Auto-Publish Feedback to Outbox (0.25 days)

**Files:**
- Modify: `tools/guild_apply.py` — `_action_complete()` saves feedback to outbox
- Test: `tests/tools/test_guild_apply.py` — verify outbox file created

**Success criteria:**
- Feedback YAML automatically written to outbox after complete
- No GitHub PR created (just staged)
- Agent still told feedback is available for review

**Verification:**
```bash
ls ~/.hermes/guild/outbox/*.feedback.yaml  # should exist after apply_complete
```

### Task 7: Integration Tests (0.5 days)

**Files:**
- Create: `tests/tools/test_guild_feedback_loop.py` — full loop integration test

**Success criteria:**
- Apply pack 5 times with mixed outcomes → confidence aggregator produces correct stats
- guild_search returns results sorted by computed_score
- Autosuggest picks highest-scoring pack
- Feedback auto-published to outbox

**Verification:**
```bash
pytest tests/tools/test_guild_feedback_loop.py -v
```

---

## 6. Success Criteria

| ID | Criterion | Measurement | Target |
|----|-----------|-------------|--------|
| SC1 | Confidence updates after apply | Apply a pack 5 times, check pack_stats.json | Confidence > "guessed" after 5 successful applies |
| SC2 | Search ranking reflects usage | Search with 2+ packs of different usage | Higher-usage pack ranks first |
| SC3 | Autosuggest filters tried packs | Apply and fail a pack, trigger autosuggest | Failed pack not re-suggested |
| SC4 | Feedback auto-published | Complete an apply session | Outbox contains feedback YAML |
| SC5 | Structured outcomes captured | Checkpoint with outcome dict | Adoption log contains phase_outcomes |
| SC6 | Backward compatible | Run existing test suite | 1073+ tests still passing |
| SC7 | No performance regression | guild_search latency | < 100ms additional from stats lookup |

---

## 7. Evaluation Plan

### 7.1 Unit Tests (per task)

Each task includes specific pytest tests. Minimum coverage:
- confidence_aggregator: 15+ tests covering all tier transitions
- structured outcomes: 5+ tests for schema validation
- search ranking: 5+ tests for ordering
- autosuggest filtering: 5+ tests

### 7.2 Integration Test

Single test that runs the full loop:
```
1. Pull a pack
2. Apply it 3 times with success (varied context_tags)
3. Apply it 2 times with failure
4. Verify pack_stats.json: total_applies=5, pass_rate=0.6
5. Verify computed_confidence is "inferred" (not "guessed")
6. Search for the pack — verify computed_score in results
7. Trigger autosuggest — verify it picks this pack
8. Apply and fail again — trigger autosuggest again
9. Verify the pack is NOT re-suggested
```

### 7.3 Eval: Does Confidence Correlate With Usefulness?

After 2 weeks of usage:
- Export pack_stats for all packs
- Compare computed_confidence vs user-reported satisfaction (if available)
- Check: do "validated" packs actually help agents more than "guessed" packs?
- Metric: average iterations_saved for validated vs guessed packs

### 7.4 Eval: Does Ranking Improve Outcomes?

A/B test (if feasible):
- Group A: autosuggest with computed_score ranking
- Group B: autosuggest with random ranking
- Measure: resolution rate after suggestion

---

## 8. Limits and Constraints

| Constraint | Description | Mitigation |
|-----------|-------------|------------|
| Single-agent aggregation | Stats only reflect this agent's experience, not network-wide | Design schema for future merge (agent_id field) |
| Free-text evidence | Structured outcomes are optional — agents may not provide them | Degrade gracefully: compute from pass/fail counts alone |
| Cold start | New packs have no stats | Default score of 0.2, self-reported confidence as fallback |
| Gaming | An agent could fake 100 successful applies | Log hash verification, rate limiting applies per session |
| File I/O | Aggregation reads all adoption_log entries — could be slow at scale | Index by pack_id, or use SQLite at >10k entries |
| Confidence oscillation | A pack at 80% pass_rate bouncing between "tested" and "inferred" | Add hysteresis: require 5+ new applies to change tier |

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agents provide garbage evidence | High | Medium | Structured outcomes supplement free-text; compute from pass/fail regardless |
| Stats file corruption | Low | High | Atomic write (write to .tmp, rename); recompute from log if corrupt |
| Performance at scale | Low (near-term) | Medium | Monitor adoption_log size; add SQLite index if >10k entries |
| Confidence scores don't match reality | Medium | High | Eval plan §7.3 — measure correlation after 2 weeks |
| Breaking existing tests | Medium | Low | SC6 — full regression suite runs after every task |

---

## 10. Timeline

| Task | Effort | Dependencies |
|------|--------|-------------|
| T1: Structured Outcome on Checkpoint | 0.5 days | None |
| T2: Enhanced Adoption Log | 0.25 days | T1 |
| T3: Confidence Aggregator | 1 day | T2 |
| T4: Search Ranking by Score | 0.25 days | T3 |
| T5: Autosuggest Enhancement | 0.25 days | T3 |
| T6: Auto-Publish Feedback | 0.25 days | None |
| T7: Integration Tests | 0.5 days | T1-T6 |
| **Total** | **3 days** | |

---

## 11. Future Extensions (Out of Scope)

- **Cross-agent aggregation:** When multiple agents publish feedback to GitHub, a central aggregator merges pack_stats across agents. Requires: network protocol, trust model for remote stats.
- **Embedding-based search:** Semantic matching using sqlite-vec embeddings (inspired by Memento-Skills). Would replace keyword matching in guild_search.
- **Pack auto-evolution:** When a phase consistently fails, auto-generate a suggested patch to the pack (e.g., split the phase, clarify checkpoint, add anti-pattern). Requires: LLM call in the aggregation loop.
- **Web dashboard:** Browse pack stats, view confidence trends, compare packs visually.
- **A/B testing framework:** Automatically test whether new packs outperform existing ones on the same problem class.
