# AI Execution Contract (Video Pipeline)

Use this contract whenever you prompt Cursor for changes in this repo.

## Why this exists

The project only earns money if quality is consistently high without manual rework.  
This contract reduces vague prompts and forces measurable delivery.

## Prompt template (copy/paste)

```md
Goal:
- [Business outcome, not just technical task]

Context:
- Files/modules in scope: [...]
- Current failure mode: [...]

Constraints:
- Linux only
- No regressions in existing pipeline flow
- Keep compatibility with current brief.json shape unless explicitly approved

Quality Bar (must pass):
- [ ] Render succeeds with >=90% planned shots
- [ ] Fallback clip path used when shot extraction fails
- [ ] SceneDetect is required in production
- [ ] Output dimensions are exactly 478x850 (9:16 target)
- [ ] No missing audio/video streams in final output
- [ ] Deterministic output when seed is provided

Deliverables:
- Code changes
- Automated tests
- Run commands
- Short risk notes

Definition of Done:
- [ ] Acceptance tests implemented and passing
- [ ] Smoke test run on a real brief
- [ ] Any assumptions documented in PRD/docs
```

## Mandatory workflow for high-quality output

For any non-trivial change, run this sequence in chat:

1. **Interview first:** ask clarifying questions before coding.
2. **Lock acceptance criteria:** measurable checks, no vague "looks good".
3. **Implement one vertical slice:** avoid broad unrelated edits.
4. **Run automated checks:** tests + reproducible command output.
5. **Summarize risk:** what can still fail and how to detect it quickly.

## Quality bar (locked from grilling session)

- **Failure strategy:** Use fallback clip and continue render.
- **Minimum shot success rate:** `>= 90%`.
- **Determinism:** Seeded behavior required (`same input + same seed => same output`).
- **SceneDetect policy:** Required in production mode.
- **Merge gate:** Automated tests required (plus smoke checks).
- **Duration tolerance:** Dependent on extracted clip behavior; define per-test with explicit bounds.

## Repo-specific request style

When asking for changes, include:

- `brief.json` example or expected shot shape.
- Whether behavior should be strict/blocking or best-effort.
- Exact command you expect to run after merge.
- One "bad output" example and one "good output" example.

## Avoid these prompt anti-patterns

- "Improve quality" with no metric.
- "Refactor everything" in one request.
- "Make it production-ready" without acceptance tests.
- "Just use your best judgment" on business-critical behavior.
