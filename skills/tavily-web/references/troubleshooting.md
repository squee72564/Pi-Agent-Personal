# Tavily CLI troubleshooting

- The helper requires Python 3 and `tvly` on PATH. If missing, ask the user to install it or reopen their terminal; do not install/update it automatically.
- `auth` captures CLI credential details and prints only a safe status. If missing/expired, ask the user to run `tvly login` locally, complete browser authentication, and tell you when done. Never inspect credential files or ask for pasted keys.
- Authentication does not guarantee quota, credits, or backend availability. Report the actual failure; do not silently switch to anonymous requests or bypass quotas.
- With tavily-cli 1.0.1, minimal `tvly --json search QUERY --max-results N` and `tvly --json extract URL` worked, while some advertised optional flags caused backend validation errors. The helper intentionally uses minimal CLI options. Its snippet/pagination flags are local, not forwarded API flags.
- Native `tvly search --max-chars` does not limit JSON/file output. The helper parses JSON outside model output, then bounds the returned text. Do not dump full JSON into context.
- Use `site:example.com`, not `site.example.com`, in search queries. Treat it as a search hint, not an enforced domain filter: verify returned URLs and content. Reject wrong entities/locations and stale timestamps even when result titles look correct.
- If extraction is empty, blocked, stale, or incomplete, explain the limitation and consider a public official Markdown source or another primary source. A non-authentication-related extraction failure can justify bounded direct fetching; do not bypass login or access controls. Keep raw HTML out of model context.
