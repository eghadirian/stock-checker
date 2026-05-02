# Scurfa Tracker Active

## Exact-product stock detection

The checker prioritizes main-product-only signals so it doesn't confuse related products, ads, or upsells with the watched item.

Signal order:
1. Product JSON-LD scoped to the exact product title (`InStock` / `OutOfStock`).
2. Enabled add-to-cart flow in the main `form.cart`.
3. Sold-out phrases in the main product container only.
4. Optional AI vote (complementary, never primary).

## Optional AI enhancement (free API-compatible)

You can complement regex/rules with a free-tier LLM/NLI classifier from Hugging Face Inference API.

Set environment variables:
- `HF_TOKEN` = your Hugging Face token
- `USE_AI_AVAILABILITY=1` (default)
- optional `HF_MODEL` (default: `facebook/bart-large-mnli`)

Why this setup:
- deterministic rules remain the source of truth;
- AI is used only as a tie-breaker/extra hint when page copy is ambiguous;
- keeps false alerts lower than pure LLM extraction.

## Library choice guidance

- **Best baseline for this project:** `requests + BeautifulSoup` + structured signals (current implementation).
- **Best parser upgrade:** `extruct` for robust schema extraction across mixed templates.
- **Use Crawl4AI** if stock state only appears after JS rendering.
- **Use ScrapeGraphAI** for broader unstructured extraction tasks, not strict binary availability alerts.
