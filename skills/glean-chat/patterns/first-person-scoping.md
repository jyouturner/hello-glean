# Pattern: first-person scoping

Glean's MCP server authenticates via the user's own SSO session. From
Glean's perspective, every query you send is *the user asking*, not an
anonymous agent. This means Glean already knows:

- The user's identity (name, email, Slack handle, employee ID)
- Their org chart position
- Their access permissions (you can only see what they can see)
- Their authored docs, sent messages, attended meetings, owned tickets

**Use this.** It's the most leveraged feature of the whole MCP.

## The right way: first-person queries

```python
glean_chat(query="What have I worked on in the last 12 months "
                   "that demonstrates technical leadership?")

glean_chat(query="Are there postmortems I authored or contributed to?")

glean_chat(query="What 1:1 notes or DMs do I have where I "
                   "coached someone through career growth?")
```

Glean auto-scopes each of these to the authenticated user. You don't pass
a name; you don't filter by author; you don't guess email patterns. Glean
just knows.

## The wrong way: passing names

```python
# BAD — fragile to name format mismatches
glean_chat(query="What did Yong Jiang contribute to the recs pipeline?")
```

If the authenticated user is "Yong Jiang" in some systems but "Jerry You"
in HD's directory, this query returns **nothing** — no error, just an
empty result set. Glean dutifully searches for "Yong Jiang" and finds no
matching directory entry, then tells you nothing was found.

Worse: if there's a *different* employee with the matching name, you'll
get *their* results and not realize.

## Confirming the user's identity is wired

If you're unsure whether SSO is working correctly, send a probing query:

```python
glean_chat(query="What's my name, role, and team according to "
                   "the directory?")
```

Glean will confirm. Once confirmed, drop name-passing entirely.

## Combining first-person with multi-turn

```python
session = "my_recent_work"

# Turn 1 — broad first-person probe
glean_chat(
  query="What have I worked on in the last 12 months at the "
        "architect or multiplier level?",
  session_id=session,
)

# Turn 2 — Glean has the list; ask for one specifically
glean_chat(
  query="Tell me more about the cost optimizer agent — when did "
        "I publish it and what specific savings has it surfaced?",
  session_id=session,
)
```

This is the workflow for "tell me about my own contributions" — both
calls pivot on first-person + session continuity.

## When name-passing is unavoidable

Asking about *other people's* contributions is name-based by necessity:

```python
glean_chat(query="What is Ankit Kothari's documented role on BBT?")
```

For these, prefer **full names + last names** as Slack/email show them,
not nicknames. If results are empty, try the inverse "First Last" vs
"Last, First" format — directories vary.

## Privacy and access

Because everything is scoped to the user's permissions, you cannot use
Glean to "snoop" on data the user can't see anyway. This is correct and
desirable — but it also means: if a query returns empty, *one possibility
is permissions, not absence*. Surface this to the user when uncertain.
