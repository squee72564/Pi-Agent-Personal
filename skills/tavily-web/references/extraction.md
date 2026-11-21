# Reading pages

Use the same `scripts/web.py` helper as for search; resolve its path relative to the skill directory.

```bash
python "<skill-directory>/scripts/web.py" extract "https://example.com/docs"
```

Defaults to 12000 characters of Tavily-extracted Markdown, not raw HTML. `--max-chars` accepts **1-25000** per call. Prefer smaller chunks for focused reading; 23000-25000 is allowed when useful. Titles, source URLs, retrieval timestamps, and truncation notices accompany content.

## Continue without refetching

`--start` is a **zero-based character offset**, not a row/line number. It can exceed 25000:

```bash
python "<skill-directory>/scripts/web.py" extract "https://example.com/docs" --start 12000 --max-chars 12000
```

Use the continuation offset printed by the previous response. Extractions are cached for one hour in the OS temporary directory. Continuation normally reads that cache without another Tavily request. `--refresh` forces a new extraction; offsets can shift after a refresh or expired cache.

Extraction preserves source wording and document layout rather than silently summarizing. Some navigation, banners, or access-warning text may remain. A successful extraction does not prove the whole webpage was captured. Check for actual relevant content, not just a login screen. Preserve dates, headings, tables, and code needed to interpret claims.

Independent pages may be extracted in parallel, but several 25000-character responses consume substantial context. Normally read one chunk before requesting its continuation. Avoid broad crawl/map/research jobs unless requested; they increase cost and output.
