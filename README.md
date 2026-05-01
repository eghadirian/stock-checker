Scurfa Tracker Active

## Auto-buy with Playwright

The checker can optionally start a Playwright-driven checkout flow when stock is detected, but only when the `--autobuy` flag is passed (default is off).

### Install

```bash
pip install requests beautifulsoup4 playwright
playwright install chromium
```

### Usage

```bash
python check_scurfa.py --autobuy
```

By default, checkout fields are filled but order submission is blocked for safety.
Set `PLACE_ORDER=true` only if you want to attempt final order placement.

### Checkout placeholders (override with env vars)

- Name/age: `CHECKOUT_FIRST_NAME`, `CHECKOUT_LAST_NAME`, `CHECKOUT_AGE`
- Contact: `CHECKOUT_EMAIL`, `CHECKOUT_PHONE`
- Shipping: `SHIPPING_ADDRESS_1`, `SHIPPING_ADDRESS_2`, `SHIPPING_CITY`, `SHIPPING_STATE`, `SHIPPING_ZIP`, `SHIPPING_COUNTRY`
- Billing: `BILLING_ADDRESS_1`, `BILLING_ADDRESS_2`, `BILLING_CITY`, `BILLING_STATE`, `BILLING_ZIP`, `BILLING_COUNTRY`
- Card: `CARD_NAME`, `CARD_NUMBER`, `CARD_EXP_MONTH`, `CARD_EXP_YEAR`, `CARD_CVV`
