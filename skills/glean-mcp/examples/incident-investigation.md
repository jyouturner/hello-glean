# Example: incident investigation

## The use case

The user wants to write up or recall an internal production incident:
customer impact, timeline, root cause, fix, and what was learned. This
content lives across Confluence postmortems, Slack incident channels,
Jira tickets, and the user's own notes.

## Workflow

### Step 1 — establish the incident shell

```python
session = "incident_atc_button"

glean_chat(
  query="Tell me about the ATC Button Disabled on B2B PIP incident "
        "from January 6, 2026 — what was the customer impact, the root "
        "cause I identified, the fix, and how long the incident lasted?",
  session_id=session,
)
```

Glean returns a structured summary with timestamps, business impact,
root-cause description, and fix details. This is enough for a 90-second
verbal incident recap.

### Step 2 — drill the failure chain

```python
glean_chat(
  query="Walk me through the technical failure chain step by step. "
        "What was the dependency that triggered it, and what surfaced "
        "where?",
  session_id=session,
)
```

Glean expands the technical detail: dependency version bumps, schema
conflicts in the data layer, downstream UI behavior. This is the depth
material for an engineering audience.

### Step 3 — find the artifacts

```python
glean_chat(
  query="What postmortem or RCA docs exist for this incident, and who "
        "authored or owns each?",
  session_id=session,
)
```

Glean returns Confluence URLs and authorship — useful for "where can I
read more" and for confirming who was on the response.

## Phrasing tips for incident queries

- **Always include the date or rough time window.** Incident searches
  return better results when scoped: "January 6, 2026" or "the
  recommendations 5xx incident from March 2026."
- **Use the impacted system name as the user wrote it.** "ATC Button
  Disabled on B2B PIP" matches the postmortem title; "Add to Cart issue
  on B2B" doesn't.
- **Ask about your role explicitly.** "What was my role in the
  diagnosis and fix?" surfaces your authored RCAs and your contributions
  to others' threads.

## What to do with the results

For interview prep, write the incident as a STAR card:

```markdown
## ATC Button Disabled — postmortem owner (2026-01-06)

**Situation.** All ATC buttons inside Recs modules on B2B PIP
disabled at ~11:10 AM EST. ~6% of PIP recs-driven orders, ~$15K/day
revenue at risk.

**Task.** Lead diagnosis under live revenue impact, contain the bleed,
own the RCA.

**Action.**
- Quantified business impact (~$15K/day)
- Traced the failure chain: Buybox v5.143.1 → v5.147.0; new add-to lib
  used different fulfillment-query schema; Nucleus detected merge
  conflict and dropped fulfillment data; ATC logic disabled buttons
- Coordinated rollback v2.1.7 → v2.1.3
- Authored 2 RCA docs

**Result.** Resolved in ~75-80 minutes; identified gaps drove follow-on
regression-testing work.

**Source:**
- "01/06/2026 - ATC Button Disabled on B2B PIP" (Confluence)
- "DataModel Conflict Analysis – ATC Buttons Disabled Issue" (personal
  Confluence)
```

Three Glean turns produced enough evidence for a complete, citable STAR
card. Same investigation by hand from memory would take significantly
longer and almost certainly miss the timeline numbers and the
dependency-version specifics.

## When the incident isn't well-documented

Sometimes Glean can't find a clean postmortem. Common causes:
- The incident was small and never got a formal write-up
- The user was peripherally involved (commented in a thread, didn't own)
- The incident pre-dates indexed history

In these cases, ask Glean for *adjacent* artifacts:

```python
glean_chat(
  query="Are there Slack threads where I discussed problems with X?",
  session_id=session,
)

glean_chat(
  query="Are there Jira tickets I filed against system X around that time?",
  session_id=session,
)
```

Tickets and Slack threads often have the raw incident details even when
no formal postmortem was written.
