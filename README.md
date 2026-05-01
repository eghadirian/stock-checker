# Scurfa Tracker Active

## Stock detection strategy (exact product only)

This checker now prioritizes **main-product-only** signals to avoid false positives from related products, ads, and upsells:

1. Reads the page's main product title (`h1.product_title`).
2. Checks Product JSON-LD (`application/ld+json`) for `InStock` / `OutOfStock`, scoped to that exact product name.
3. Verifies an enabled add-to-cart control inside the **main product** `form.cart` only.
4. Uses sold-out text only from the main product container (not global page text).

## Library research and recommendation

For this specific use case (binary in-stock checks on one product URL), these are the best practical options:

- **Best default: BeautifulSoup + structured-data checks (current approach)**
  - Reliable for WooCommerce product pages.
  - Fast, low-cost, deterministic.
  - No LLM/API dependency.

- **Best upgrade for schema reliability: `extruct`**
  - Purpose-built for extracting JSON-LD/microdata/RDFa.
  - Great when themes change markup often.
  - Recommended if you monitor many stores with mixed templates.

- **When to use Crawl4AI**
  - Strong for JS-heavy pages and broader crawling workflows.
  - Heavier runtime (Playwright/browser) than needed for one product check.

- **When to use ScrapeGraphAI**
  - Useful for unstructured extraction tasks across many unknown site layouts.
  - LLM-based extraction can be less deterministic for strict stock/not-stock alerting.

### Practical recommendation

- Keep this script as baseline for Scurfa/WooCommerce pages.
- Add `extruct` if you want more robust structured-data parsing.
- Move to Crawl4AI only if the target site requires rendered JavaScript to expose stock state.
