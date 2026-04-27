# Pattern: multi-turn drill

Glean carries chat context across calls that share a `session_id`. The
right unit of work is a **conversation**, not a query.

## The shape

```
[ broad probe ] → [ targeted follow-up ] → [ deeper follow-up ] → ...
        ^                  ^                       ^
        same session_id    same session_id         same session_id
```

After the broad probe, Glean has indexed the relevant docs and you have
the lay of the land. Each follow-up costs less context-establishment work
and goes deeper.

## Worked example: STAR-mining a single project

**Goal:** get rich evidence about the user's role on Project Foo so you
can write a STAR-format interview answer.

```python
session = "research_foo"

# Turn 1 — broad probe; let Glean tell you what's there
glean_chat(
  query="What is my documented role on Project Foo? "
        "What decisions did I drive or approve?",
  session_id=session,
)
# → returns: "You authored the architecture doc X and Y, made the call on
#   Z, set ownership boundaries between teams A and B..."

# Turn 2 — drill into the most useful thread
glean_chat(
  query="Tell me more about decision Z — when did I make it, "
        "who pushed back, and what was the outcome?",
  session_id=session,
)
# → returns: "On 2026-02-04 in #recs-leaders thread, you said... "

# Turn 3 — pull artifacts
glean_chat(
  query="What docs back this up? Confluence pages, Slack threads, "
        "or Jira tickets I can cite?",
  session_id=session,
)
# → returns: "Here are the artifacts: [Confluence page URL], [Slack
#   permalink], [Jira ticket]..."
```

Three calls produce a citation-grade STAR anchor. The same information via
fan-out one-shots would take 6-8 calls and lose continuity between them.

## Worked example: investigating an incident

```python
session = "incident_atc_button"

# Turn 1 — establish the incident shell
glean_chat(
  query="Tell me about the ATC Button Disabled on B2B PIP "
        "incident — what happened, customer impact, root cause?",
  session_id=session,
)

# Turn 2 — dig into the failure chain
glean_chat(
  query="Walk me through the failure chain step by step. "
        "What dependency caused it?",
  session_id=session,
)

# Turn 3 — get the timeline
glean_chat(
  query="What was the timeline from detection to resolution?",
  session_id=session,
)

# Turn 4 — get artifacts
glean_chat(
  query="Where are the postmortem docs? Who authored each?",
  session_id=session,
)
```

## When NOT to drill

If the question is genuinely a one-shot fact lookup ("what is the URL of
our recs runbook?"), one turn is enough. Don't pad. Multi-turn is for
*depth*, not for show.

## Pitfalls

- **Restating the topic on every turn.** Glean already has it. Use
  pronouns: "its cost", "that decision", "the team that owned it." Saves
  tokens and reads natural.
- **Drilling on a thread that's actually empty.** If Glean returns "I
  couldn't find evidence of X," don't drill — pivot to a different angle
  or accept the negative result.
- **Letting the conversation wander.** If you find yourself asking
  unrelated questions, you've drifted out of "drill" mode and into "new
  topic" — open a new session.
