# Example: multi-faceted research on one topic

## The use case

The user has one topic in mind (a project, a system, a person, a
decision) and wants several distinct angles on it: architecture +
ownership + historical decisions + outcomes + risks. Each angle is its
own question, but they share context.

## Workflow

Use **one session_id** with sequential drills. Each turn focuses on one
angle and benefits from prior context.

### Worked example — researching a project (BBT)

```python
session = "research_bbt_full"

# Angle 1 — what it is
glean_chat(
  query="What is BBT (Beyond Bought Together)? Give me the elevator "
        "pitch and the production status.",
  session_id=session,
)

# Angle 2 — architecture (Glean knows we're talking about BBT now)
glean_chat(
  query="What is its architecture end-to-end? Walk me through the "
        "stages.",
  session_id=session,
)

# Angle 3 — ownership and contributors
glean_chat(
  query="Who is named in the PRD and 1-pager? Who leads engineering, "
        "who leads DS, who are the technical contacts?",
  session_id=session,
)

# Angle 4 — what is my role
glean_chat(
  query="What is MY documented role on it? What decisions did I drive, "
        "approve, or shape?",
  session_id=session,
)

# Angle 5 — model decisions
glean_chat(
  query="What were the model decisions — Pro vs Flash, judging vs "
        "generation? What were the eval numbers?",
  session_id=session,
)

# Angle 6 — incidents and lessons
glean_chat(
  query="Have there been production incidents on it? What was learned?",
  session_id=session,
)
```

Six turns, one session, one topic. Each turn returns rich evidence about
its angle. Together they give you a 360° view of the project.

## Why one session beats six parallel one-shots

Compare the same six angles run as fan-out one-shots:

```python
# Anti-pattern — fan-out one-shots
glean_chat(query="What is BBT?", session_id="bbt_1")
glean_chat(query="What is the architecture of BBT?", session_id="bbt_2")
glean_chat(query="Who is named in the BBT PRD?", session_id="bbt_3")
glean_chat(query="What is my role on BBT?", session_id="bbt_4")
glean_chat(query="What were the BBT model decisions?", session_id="bbt_5")
glean_chat(query="Have there been BBT incidents?", session_id="bbt_6")
```

Problems:
- Each query has to re-establish "BBT" context internally (slower)
- Pronouns aren't available — every query repeats "BBT" or "Beyond
  Bought Together" (more tokens, less natural)
- You can't reference Turn 2's findings in Turn 3's question (no
  drilling on a thread)
- 6 separate permission prompts in interactive flows (annoying)

## When this pattern is wrong

Don't use sequential drills if the angles are *unrelated* — separate
topics deserve separate sessions. The test: would the next question
benefit from prior context, or is it independent?

```python
# These are independent topics → separate sessions
glean_chat(query="What's my BBT role?", session_id="bbt_role")
glean_chat(query="What's the on-call rotation?", session_id="oncall")
```

## Combining sessions and parallelism

For a complex investigation with multiple independent topics, each
having multiple angles, you can do **parallel sessions, each with
sequential drills inside**:

```
session: "research_bbt"      → 6-turn drill
session: "research_peva"     → 5-turn drill
session: "research_oncall"   → 4-turn drill
```

The three sessions can run in parallel; each drill happens sequentially
within its own session. This is the optimal shape for a wide-and-deep
research task.

## Real example: weekly newsletter (cross-reference)

The weekly-team-newsletter workflow is a tight version of the
sequential-drill shape: one broad cross-source probe + 1-2 audience-tuned
follow-ups in the same session. See
[weekly-team-newsletter.md](weekly-team-newsletter.md) for the full
walkthrough with real Glean output.
