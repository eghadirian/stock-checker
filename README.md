# Scurfa Tracker Active

## URL and quantity configuration

The checker no longer hardcodes a single product URL. It reads an Excel workbook with these columns:

| column | meaning |
| --- | --- |
| `url` | Product page to check. Must start with `http://` or `https://`. |
| `number` | How many units you want to buy. Blank values default to `1`. |

By default, the workbook is stored at:

```text
private/stock_urls.xlsx
```

Run the checker once to create a blank workbook template, then add rows under the `url` and `number` headers.

You can override the workbook location with `STOCK_URLS_XLSX`:

```bash
STOCK_URLS_XLSX=/secure/path/stock_urls.xlsx python check_scurfa.py
```

The script creates the workbook parent directory with private permissions and applies a private file mode to the workbook. The default workbook mode is `0600`, which means only the owning user can read and write the file. If you want a trusted Unix group to have read/write access, place the file in a group-owned directory and set:

```bash
STOCK_URLS_FILE_MODE=0660 STOCK_URLS_XLSX=/secure/path/stock_urls.xlsx python check_scurfa.py
```

Keep the real workbook out of git. The repository ignores `private/` and `*.xlsx` so only people with filesystem or deployment secret access to the workbook path can read or write the URL list.

## Quantity handling

For each configured URL, the checker uses the `number` column as the desired purchase quantity. When the page exposes an available quantity (for example a quantity input maximum or text such as `Only 2 left`), notifications use the smaller of:

1. the desired `number`, and
2. the detected available quantity.

If the page is in stock but does not expose an exact available quantity, the notification uses the requested `number`.

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
