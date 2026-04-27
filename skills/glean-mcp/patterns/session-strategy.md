# Pattern: session strategy

`session_id` is the unit of conversational continuity. Two queries with
the same `session_id` are *the same chat*; two with different IDs are
different chats. Get this right and you save calls + get better answers.

## The mental model

| Same `session_id` | Different `session_id` |
|---|---|
| Same chat — Glean remembers prior turns | Independent chats — no shared context |
| Pronouns resolve | Pronouns are unresolved |
| Glean can "drill in" | Each query stands alone |
| Use for: depth on one topic | Use for: independent questions |

## When to keep one session

- You're asking follow-up questions about the same project / system / person
- The next question naturally uses pronouns ("its cost", "that decision")
- You want Glean to build context progressively

## When to start a new session

- You're switching to an unrelated topic
- You want a "fresh take" without prior-turn anchoring
- You're running parallel research streams (one per project, one per
  topic) and don't want them to interfere

## Naming sessions for your future self

`session_id` is a free string. Use names that signal intent:

```python
"research_peva_demo"        # one project, one angle
"research_peva_cost"        # same project, different angle (separate)
"research_bbt_full"         # different project, drill across angles
"incident_atc_button"       # incident-specific
"manager_io_pivot"          # the manager → IC pivot question
```

This also helps when reading transcripts later — you can tell at a
glance which session_id corresponded to which line of inquiry.

## Resetting a session

If you want to start fresh on the same `session_id` — e.g., reuse it for
a different topic without losing the readable name:

```python
glean_reset_session(session_id="research_peva_demo")
# next call with this session_id starts fresh
```

In practice, opening a new `session_id` is usually simpler than resetting.

## Parallel sessions vs sequential drills

There's a tension between (a) running many sessions in parallel for speed
and (b) drilling within one session for depth. The right choice depends
on whether the topics are *independent*.

**Parallel** — for genuinely independent questions that don't share
context:
```python
# These have nothing to do with each other; fire in parallel
glean_chat(query="What did I author on BBT?", session_id="bbt_role")
glean_chat(query="What's the on-call rotation?", session_id="oncall")
glean_chat(query="Have I had production incidents?", session_id="incidents")
```

**Sequential drill** — for one topic with multiple angles:
```python
# All about BBT; drill within one session
glean_chat(query="What is my role on BBT?", session_id="bbt_drill")
glean_chat(query="What were the model decisions?", session_id="bbt_drill")
glean_chat(query="What were the cost decisions?", session_id="bbt_drill")
glean_chat(query="Who else was named in the PRD?", session_id="bbt_drill")
```

The sequential drill is **higher quality per token** when the angles
relate, because each turn benefits from prior context. Use parallel when
the topics are truly independent.

## Anti-pattern: 12 parallel sessions for one investigation

When mining a project from many angles, the temptation is to fire 12
parallel queries for speed. Resist it:

- Each parallel query has to re-establish context (slower per-query
  internally)
- You can't reference Turn 2's findings in Turn 3's question
- Permission prompts can pile up

Better: one session, broad probe first, then 4-6 follow-ups in sequence.
You'll get richer evidence in fewer total tokens.

## Session lifetime

Sessions persist for the lifetime of the MCP server connection (or until
explicitly reset). When the MCP server restarts, all sessions clear.
Don't rely on session continuity across server restarts — re-establish
context if needed.
