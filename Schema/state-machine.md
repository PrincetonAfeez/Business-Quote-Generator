# Quote Status State Machine

```text
draft ──► sent ──► viewed ──► accepted
   │        │         │   └──► declined
   │        │         └──────► expired
   │        └───────────────► accepted / declined / expired
   └────────────────────────► expired
```

## Final statuses

- accepted
- declined
- expired

Once a quote leaves `draft`, the normal application UI treats the quote as locked for header and line-item editing.
