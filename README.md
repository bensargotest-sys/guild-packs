# Guild Packs

Shareable reasoning artifacts for AI agents. With proof gates.

## The Problem

AI agents save skills and prompts. But there's no way to know if a shared skill actually works. No evidence. No failure cases. No confidence level. Prompt graveyards everywhere.

## The Fix

Every shared artifact carries proof:

```yaml
confidence: tested          # guessed | inferred | tested | validated
evidence: "Reduced debugging iterations from 5+ to 2-3"
failure_cases:
  - "Heisenbugs where debugging changes behavior"
  - "Closed-source code where inspection is impossible"
```

Nothing gets adopted without knowing: who made it, what problem it solved, how confident they are, and where it breaks.

## Artifact Types

**Workflow Pack** — A domain-specific way of thinking. Not a prompt. A structured approach with phases, checkpoints, anti-patterns, and evaluation criteria.

**Critique Rubric** — How to judge output quality in a domain. Weighted criteria with good/bad examples.

**Learning Delta** — The smallest publishable improvement. Before/after with evidence.

## Format

YAML files. Each artifact has a `type` field and proof gate fields. Compatible with Hermes SKILL.md frontmatter (just add `confidence`, `evidence`, `failure_cases` to your existing skills).

## Examples

See `examples/` for 3 real workflow packs retrofitted from production Hermes skills:
- `systematic-debugging.workflow.yaml` — 4-phase root cause investigation
- `code-review.workflow.yaml` — Security-first review checklist
- `plan.workflow.yaml` — Read-then-write planning discipline

Each has a companion `.rubric.yaml` with weighted evaluation criteria.

## Using a Pack

1. Read the workflow pack
2. Check `confidence` and `failure_cases` — does it apply to your situation?
3. Use the phases as your approach
4. Evaluate your result against the companion rubric
5. If it worked, publish a Learning Delta back

## Publishing a Pack

Your pack needs:
- `confidence` — be honest. "guessed" is fine for new approaches.
- `evidence` — what measurably improved? "It felt better" doesn't count.
- `failure_cases` — where does this break? If you don't know, say so.

## Integration

Works with any agent system. For Hermes agents, the proof gate fields (`confidence`, `evidence`, `failure_cases`) are validated in the skill manager as of v0.1.

## License

MIT
