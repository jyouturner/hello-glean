# Pattern: natural-language questions, not keyword bags

Glean is an LLM-backed chat agent. When you give it keywords, it
*topic-guesses* — it tries to be helpful by riffing on the implied topic.
When you give it a question, it engages with the question and returns
specific evidence.

The difference is large.

## Demonstration

**Keyword bag:**
```
PEVA visual QA agent demo Slack
```

What Glean does: searches for related docs, then *generates a generic
tutorial* on how someone might demo PEVA — because it interprets the
keywords as "the user wants to know about PEVA demos."

**Same query, as a question:**
```
Has the PEVA visual QA agent ever been demoed internally? If so, who saw
it, and what was the documented reception?
```

What Glean does: searches calendars, Slack channels, Confluence demo
recap pages, DMs — and answers the *actual question* with specific
evidence ("informal share in #tmp-recs-regression-testing on date X;
1:1 walkthrough with [name] on date Y; no formal demo recorded").

## Anatomy of a good question

| Element | Why |
|---|---|
| Verb form ("Has X happened?", "What was Y?") | Forces Glean to engage with truth-conditions, not topic |
| Specific entities (project names, people, systems) | Disambiguates which corner of the org to search |
| Time context if relevant ("in the last 12 months", "before Q3") | Constrains the search window |
| What evidence you want ("with citations", "in dollars per month") | Glean tailors output to the form you need |

## Templates that work well

**"Has X happened?"**
```
Has the BBT pipeline ever had a production incident reported by me?
```

**"What was the documented decision/outcome of X?"**
```
What was the documented decision on Pro vs Flash for spec generation
in BBT? Where is the eval data?
```

**"Tell me about my role on X — what did I drive, approve, or shape?"**
```
What is my documented role on the Recs Platform 2026 strategy?
What decisions did I drive, approve, or shape?
```

**"Walk me through X with concrete details."**
```
Walk me through the ATC Button Disabled incident — customer impact,
root cause, timeline, and fix.
```

**"Who authored / owns / leads X?"**
```
Who is named as the engineering lead and DS lead for BBT in the PRD?
```

## What to avoid

- **Single-noun queries** ("PEVA", "BBT") — too broad; Glean just gives
  you a wikipedia-style summary
- **Boolean operators** (`PEVA AND demo NOT roadmap`) — Glean is a chat
  agent, not Lucene. Just ask.
- **Stuffing too much into one turn** ("Tell me about PEVA's
  architecture, cost, demos, and team and decisions and incidents
  and...") — split across turns for depth
- **Field qualifiers** (`from:me`, `app:slack`) — Glean uses these
  internally, but you don't need to. Asking "what have I posted in Slack
  about X?" is enough; Glean will translate.

## Iteration is fine

If the first phrasing returns generic content, *don't escalate* — refine.
Same session_id, narrower question:

```
Turn 1: "Tell me about PEVA."
        → returns generic overview
Turn 2: "Specifically — has it run in production, and if so, when did
        it ship?"
        → returns specific evidence
```

This is the multi-turn drill (see [multi-turn-drill.md](multi-turn-drill.md)).
