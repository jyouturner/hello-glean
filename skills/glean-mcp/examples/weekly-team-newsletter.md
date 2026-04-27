# Example: weekly team newsletter

## The use case

You're a manager, EM, principal, or team lead and you need to write a
weekly newsletter to your stakeholders or team summarizing:

- What shipped this week
- Major decisions / designs landed
- What's notably in flight
- Cross-team activity worth flagging
- Maybe kudos / wins

By hand, this takes 60-90 minutes — toggling between Jira filters,
GitHub PR lists, Confluence "recently updated," and Slack scroll-back —
and you almost always miss something.

Glean does it in 1-3 calls because it indexes all those sources and
already knows your team via SSO + the org chart.

## Why Glean is uniquely good at this

Glean ties together:
- **Jira** — tickets your team closed or moved this week
- **GitHub** — PRs your reports merged or opened
- **Confluence** — pages your team authored or updated
- **Slack** — major threads your team participated in
- **Calendar** — meetings of note (less often useful for newsletters)
- **Directory + reporting graph** — auto-resolves "my team" via SSO

You don't have to specify any of those individually. One natural-language
question gets all of it.

## Workflow

### Step 1 — one broad probe

```python
session = "weekly_newsletter_2026_w17"

glean_chat(
  query="What has my team shipped or made notable progress on in the "
        "past week (April 18-25, 2026)? Cover Jira tickets closed, PRs "
        "merged, Confluence pages authored, and major Slack discussions.",
  session_id=session,
)
```

What Glean does internally (visible in its progress log):
- Searches Jira for closed/in-progress tickets in the date window, scoped
  to your direct reports
- Searches GitHub for merged PRs from your reports
- Searches Confluence for recently authored or updated pages owned by
  your team
- Searches Slack for major threads your team participated in
- Cross-references across sources to build a coherent narrative

What it returns: a structured newsletter draft, organized by source
(Jira / GitHub / Confluence / Slack), with named contributors per item
and ticket numbers / PR numbers / doc titles you can link to. Often 1-2
pages of content from a single call.

Sample shape of the response (abbreviated from a real run):

```
### Jira tickets – closed / materially advanced

Closed / Done
- DIG-232 – Secure Flow: Rex API and Recs Common Service using Rivet
  (Samba). Migrated CI/CD for a large set of recs services... Status
  Done as of Apr 21.
- DIG-89 – Deals Hardcoded in DRecs: Discovery (Biniam). Completed gap
  analysis and migration plan to move /deals from Dynamic Recs into
  rex-api... Status Done as of Apr 22.
- ...

In progress but notable
- DIG-244 – Deals: Category-only mode, filtering & distribution (Biniam)
- DIG-261 – ATC & BIA Pipelines Machine Type Upgrades (Biniam)
- ...

### GitHub PRs – merged / major progress

Biniam – ATC & BIA pipelines
- ocm_recs-atc-ranking-model #76 — productionizes the ATC ranking
  model pipeline. Merged Apr 22.
- ...

Samba – Secure Flow & Rivet
- DIG-236: secureflow fanout (rivet #11) – Merged Apr 22.
- ...

### Confluence – new / updated pages

- Dataflow/Dataproc Java upgrade steps (Selvaraj)
- Java 21 Migration – product-details-loader (Soumya)
- ...

### Major Slack discussions

- Access for analytics-mkt-cleanroom to personalization stage
  (CLOUD-29058 → SSRE-1468)
- Cost & access patterns around pr-spa-datalake-multi-region
- ...
```

This is already a complete newsletter draft. For most weeks, you can
copy-paste-edit and ship.

### Step 2 — drill for the audience

Newsletters are audience-specific. The same week's work matters to a
director differently than to peer teams or to your own engineers. Drill
within the same session:

```python
glean_chat(
  query="From those, pick the 2-3 items that would matter most to a "
        "director-level audience and explain why each matters in "
        "business terms.",
  session_id=session,
)
```

Because Glean already has Turn 1's content in context, it doesn't have
to re-search — it ranks and reframes the existing items. Sample output
(abbreviated from a real run):

```
For a director-level audience, these 3 items have the clearest business
impact:

1. Secure Flow migration for recs/search services (DIG-232 + Rivet)
   Why it matters: Risk + compliance (paved-road security, fewer audit
   findings); Change velocity (less friction per repo); Operational
   leverage (batch migration brings dozens of repos to compliance with
   the effort of a few).

2. DRecs /deals → Rex-API migration (DIG-89, DIG-244, DIG-245)
   Why it matters: Legacy retirement (prerequisite for shutting down
   DRecs, lowers run-cost); Customer experience (preserves or improves
   fair-distribution and cardinality controls); Performance SLAs (faster
   category-only path with parity tests and latency baselines).

3. ATC & Buy-It-Again pipeline upgrades (DIG-261)
   Why it matters: Cost vs. performance (n1 → n2 high-mem improves
   throughput per dollar); Revenue impact (ATC and BIA are money lanes);
   Execution readiness (cleaner footing for upcoming experimentation).
```

This is director-ready prose with business framing — much higher quality
than what you'd write quickly by hand at week's end.

### Step 3 — drill for tone (optional)

If you want a peer-team or stakeholder version:

```python
glean_chat(
  query="Now write the same items but in a tone aimed at peer engineering "
        "managers — emphasize blockers, dependencies, and where they "
        "might be affected.",
  session_id=session,
)
```

Or for your own team:

```python
glean_chat(
  query="Now phrase the wins as kudos for the people who shipped them, "
        "by name, suitable for an internal team Slack post.",
  session_id=session,
)
```

Each turn benefits from prior context. Three turns = three audience-tuned
versions of the same week's work.

## Saving the output

Pipe the output into your newsletter system (or just copy-paste). The
date-stamped `session_id` (e.g., `weekly_newsletter_2026_w17`) makes it
easy to revisit a previous week's session if you need to amend it.

## Anti-patterns to avoid

- **Searching one source at a time.** Don't do "what Jira closed this
  week," then "what PRs merged this week," then "what Confluence
  changed." Glean does cross-source synthesis far better when asked
  once. Single broad question wins.
- **Forgetting the date window.** Always include the date range
  explicitly ("April 18-25, 2026"). Otherwise Glean has to guess what
  "this week" means relative to its own search timestamp.
- **Re-running the same query if Turn 1 was light.** If Turn 1 missed
  something, **drill** in the same session ("you didn't mention the
  X work — what's its status?") rather than re-querying from scratch.
- **Asking for "everything."** Constrain by audience or domain. "What
  did everyone in the company ship?" is too broad; "what did my team
  ship that's relevant to ATC pipeline performance?" is right-sized.

## Adapting this to your team

Customize Turn 1's question to match your team's shape:

- **Replace "my team"** with your team name if SSO scoping isn't
  perfect, or to constrain to a sub-team (e.g., "the recs platform
  team")
- **Add a domain** to focus the search ("...that touches checkout
  flows" or "...related to the AI agent initiative")
- **Add a constraint** ("...excluding KTLO and dependency-bump tickets")
- **Constrain audience upfront** ("...phrased for a quarterly business
  review")

Glean handles all of these naturally because they're just clarifications
to the question.

## Why this scales

A newsletter that takes 60-90 minutes by hand takes 5-10 minutes through
Glean — and the output is usually higher quality because Glean catches
the long-tail items you'd forget. The time savings compound: weekly
newsletter, monthly recap, quarterly review. Same workflow, different
date window.
