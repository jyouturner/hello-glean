---
name: glean-chat
description: |
  Use whenever calling the Glean MCP tools (`glean_chat`, `glean_reset_session`).
  Glean is a CHAT agent, not a search engine — multi-turn within a session_id,
  SSO already knows the user's identity, and natural-language questions beat
  keyword bags by a wide margin. Load this skill before drafting any Glean
  query so the calls are well-shaped.
---

# Glean MCP — Operating Manual

The MCP tool is `glean_chat`, and the name is doing real work: Glean is a
**chat agent backed by your organization's knowledge graph** — Confluence,
Slack, Jira, Google Drive, GitHub, calendars, the directory, and more. It
is not a keyword search engine. Treating it like one gets shallow, generic
answers. Treating it like a knowledgeable colleague you can chat with gets
deep, cited, specific answers.

This skill packages the non-obvious operating model so any agent can use
the MCP effectively from the first call.

---

## The five rules

### 1. Phrase queries as questions, not keywords

**Bad** (keyword bag):
```
PEVA visual QA agent demo Slack
```

**Good** (natural-language question):
```
Has the PEVA visual QA agent ever been demoed internally?
If so, who saw it and what was the documented reception?
```

Why: the keyword form makes Glean topic-guess and produce a generic
tutorial. The question form makes Glean engage with what you actually want
to know and return specific evidence.

See [patterns/keyword-vs-question.md](patterns/keyword-vs-question.md).

### 2. Use multi-turn within a single `session_id`

Glean carries chat context across calls that share a `session_id`. Pronouns
resolve. Prior topic stays in scope. You can drill progressively:

```
Turn 1: "Tell me one sentence about PEVA."
Turn 2: "What's its biggest cost-savings number?"   ← "its" resolves to PEVA
Turn 3: "Who else is involved in shipping it?"      ← still PEVA
```

This beats fan-out one-shot queries for any topic where you want depth.
One broad probe + 2-3 targeted follow-ups is usually optimal.

See [patterns/multi-turn-drill.md](patterns/multi-turn-drill.md).

### 3. Use first-person; don't pass names

Glean knows who's authenticated via SSO. The phrase "what did **I** work
on" auto-scopes to the user. Passing names is **fragile** — if the
authenticated user goes by a different name in HD's directory than what
you guessed, the query silently returns nothing.

```
Bad:  "What did Yong Jiang contribute to the recs pipeline?"
       (returns empty if Glean knows the user as "Jerry You")

Good: "What have I contributed to the recs pipeline?"
       (auto-scopes via SSO regardless of name format)
```

See [patterns/first-person-scoping.md](patterns/first-person-scoping.md).

### 4. Reset between unrelated topics

Same `session_id` = continuing chat. New unrelated question = new
`session_id` (or call `glean_reset_session(session_id)`). Otherwise prior
context contaminates the new question.

```
session_id="research_a"  →  PEVA mining (turns 1-N)
session_id="research_b"  →  BBT mining (turns 1-N)   ← different topic, different ID
```

See [patterns/session-strategy.md](patterns/session-strategy.md).

### 5. Trust and cite the artifacts Glean returns

Glean's responses include source citations: Confluence pages, Slack
threads (with permalinks), Jira tickets, Google Docs, GitHub files. Those
are the **source of truth**. Quote numbers from them, link to them in
your output, and surface them to the user — don't paraphrase as if Glean
itself were the source.

---

## Anti-patterns to avoid

| Anti-pattern | What goes wrong | Do this instead |
|---|---|---|
| One-shot keyword bag for a complex question | Glean topic-guesses; returns generic content | Multi-turn within a session, natural-language questions |
| 12 parallel sessions when 1 would do | Wasteful; loses continuity; makes the user approve N permission prompts | One session + 3-5 follow-ups |
| Searching by name when SSO would work | Silently empty results if name format mismatches directory | Use "I/my/me"; let SSO scope |
| Treating Glean output as authoritative without citations | Hallucinations creep in; user can't verify | Quote and link the underlying artifact |
| Re-asking the same question across sessions | Slow, expensive, and loses any depth gained from prior turns | Pin the answer in your scratchpad/memory and reference back |
| Restating the topic on every turn within a session | Wasted tokens; Glean already has it | Use pronouns and short follow-ups |

---

## When to load this skill

- Before drafting any `glean_chat` query
- When the user asks for "research" or "background" on someone or something internal
- When mining for STAR-format behavioral examples, postmortems, decisions, or attribution
- When trying to find a specific artifact (doc, Slack thread, ticket) the user vaguely remembers

## When NOT to use Glean

- For external/public knowledge — Glean indexes only the org's data sources
- When the user already has the artifact in front of them — read it directly
- For very fresh content — there's some indexing lag (minutes to hours)

---

## Practical workflows

The [examples/](examples/) directory shows complete end-to-end patterns:

- [weekly-team-newsletter.md](examples/weekly-team-newsletter.md) —
  one broad probe + 1-2 audience-tuned drills replaces 60-90 minutes of
  manual Jira/GitHub/Confluence/Slack scrolling. Real run included.
- [incident-investigation.md](examples/incident-investigation.md) —
  mining postmortems, RCAs, and incident threads where the user was
  involved.
- [multi-faceted-research.md](examples/multi-faceted-research.md) —
  when a single topic has multiple angles (architecture + ownership +
  decisions + outcomes) and you want all of them.

---

## Quick reference card

| If you want… | Do this |
|---|---|
| A specific fact about an internal system | Single natural-language question, fresh session_id |
| Depth on a topic | Multi-turn: broad probe → 2-3 follow-ups, one session_id |
| What the user has done | First-person query ("what have I…") |
| Multiple angles on one topic | Multi-turn within one session_id, drilling each angle as a turn |
| Independent topics | Multiple session_ids, in parallel |
| Fresh start on the same topic | `glean_reset_session(session_id)` |
| Verify a returned claim | Read the cited artifact directly (URL is in the response) |
