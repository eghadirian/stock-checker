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

### What these variables are

- `HF_TOKEN`: your Hugging Face access token used to call the Inference API.
- `HF_MODEL`: model id to query (default: `facebook/bart-large-mnli`).
- `USE_AI_AVAILABILITY`: feature flag (`1` enabled, `0` disabled).

### Where values should be loaded from

They should be loaded from **environment variables** (already implemented in `check_scurfa.py`).
That means you should **not hardcode** them in source files.

### Where to get them

1. Create a Hugging Face account: https://huggingface.co/
2. Create a token in Settings → Access Tokens.
3. Use that token as `HF_TOKEN`.
4. Keep `HF_MODEL` as default unless you want to test alternatives.

### Can these be repo secrets?

Yes — and that is the recommended approach for CI/GitHub Actions.

Use repository secrets such as:
- `HF_TOKEN`
- `HF_MODEL` (optional; only if you want to override default)
- `USE_AI_AVAILABILITY` (optional; default is already `1`)

In GitHub Actions, map secrets to env vars, for example:

```yaml
env:
  HF_TOKEN: ${{ secrets.HF_TOKEN }}
  HF_MODEL: ${{ secrets.HF_MODEL }}
  USE_AI_AVAILABILITY: ${{ secrets.USE_AI_AVAILABILITY }}
```

If `HF_TOKEN` is missing, the script safely skips AI and continues with deterministic checks.

## Library choice guidance

- **Best baseline for this project:** `requests + BeautifulSoup` + structured signals (current implementation).
- **Best parser upgrade:** `extruct` for robust schema extraction across mixed templates.
- **Use Crawl4AI** if stock state only appears after JS rendering.
- **Use ScrapeGraphAI** for broader unstructured extraction tasks, not strict binary availability alerts.
