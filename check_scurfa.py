import os
import random
import re
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_WORKBOOK_PATH = BASE_DIR / "private" / "stock_urls.xlsx"
WORKBOOK_PATH = Path(os.environ.get("STOCK_URLS_XLSX", DEFAULT_WORKBOOK_PATH)).expanduser()
WORKBOOK_FILE_MODE = int(os.environ.get("STOCK_URLS_FILE_MODE", "0600"), 8)
DEFAULT_PURCHASE_NUMBER = int(os.environ.get("DEFAULT_PURCHASE_NUMBER", "1"))
NTFY_TOPIC = "scurfa_yellow_titan_2026"

# Optional AI signal via Hugging Face Inference API (free tier available with token)
HF_TOKEN = os.environ.get('HF_TOKEN')
HF_MODEL = os.environ.get('HF_MODEL', 'facebook/bart-large-mnli')
USE_AI_AVAILABILITY = os.environ.get('USE_AI_AVAILABILITY', '1') == '1'

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')


@dataclass(frozen=True)
class WatchItem:
    url: str
    desired_number: int


def _xlsx_cell(column, row, value):
    return (
        f'<c r="{column}{row}" t="inlineStr">'
        f'<is><t>{xml_escape(str(value))}</t></is>'
        '</c>'
    )


def _private_parent_mode():
    return 0o770 if WORKBOOK_FILE_MODE & 0o070 else 0o700


def create_workbook_template(path):
    """Create a minimal .xlsx file with url and number columns, without external deps."""
    path.parent.mkdir(mode=_private_parent_mode(), parents=True, exist_ok=True)
    os.chmod(path.parent, _private_parent_mode())

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="urls" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''
    sheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData><row r="1">{_xlsx_cell('A', 1, 'url')}{_xlsx_cell('B', 1, 'number')}</row></sheetData>
</worksheet>'''

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as workbook_zip:
        workbook_zip.writestr("[Content_Types].xml", content_types)
        workbook_zip.writestr("_rels/.rels", root_rels)
        workbook_zip.writestr("xl/workbook.xml", workbook)
        workbook_zip.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        workbook_zip.writestr("xl/worksheets/sheet1.xml", sheet)

    os.chmod(path, WORKBOOK_FILE_MODE)


def ensure_private_workbook(path=WORKBOOK_PATH):
    """Ensure the workbook exists and is not world-readable/writable."""
    path = Path(path).expanduser()
    if not path.exists():
        create_workbook_template(path)
        print(f"Created private workbook template at {path}. Add rows with columns: url, number.")
    else:
        if path.is_file():
            os.chmod(path, WORKBOOK_FILE_MODE)
        if path.parent.exists():
            current_parent_mode = path.parent.stat().st_mode & 0o777
            owner_and_group_mode = current_parent_mode & ~0o007
            if WORKBOOK_FILE_MODE & 0o070:
                owner_and_group_mode |= 0o770
            else:
                owner_and_group_mode &= ~0o070
            os.chmod(path.parent, owner_and_group_mode)

    file_mode = path.stat().st_mode & 0o777
    if file_mode & 0o007:
        raise PermissionError(f"Workbook {path} is accessible to other users (mode {file_mode:o}).")
    return path


def _xlsx_text(cell, shared_strings):
    namespace = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    cell_type = cell.attrib.get('t')

    if cell_type == 's':
        value = cell.findtext(f'{namespace}v')
        if value is None:
            return ''
        return shared_strings[int(value)]

    if cell_type == 'inlineStr':
        inline = cell.find(f'{namespace}is')
        return ''.join(inline.itertext()).strip() if inline is not None else ''

    value = cell.findtext(f'{namespace}v')
    return value.strip() if value else ''


def _xlsx_column_name(cell_ref):
    match = re.match(r'([A-Z]+)', cell_ref or '')
    return match.group(1) if match else ''


def _load_shared_strings(workbook_zip):
    try:
        raw = workbook_zip.read('xl/sharedStrings.xml')
    except KeyError:
        return []

    namespace = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    root = ET.fromstring(raw)
    strings = []
    for item in root.findall(f'{namespace}si'):
        strings.append(''.join(item.itertext()).strip())
    return strings


def _worksheet_rows(path):
    namespace = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    with zipfile.ZipFile(path) as workbook_zip:
        shared_strings = _load_shared_strings(workbook_zip)
        sheet = ET.fromstring(workbook_zip.read('xl/worksheets/sheet1.xml'))

    rows = []
    for row in sheet.findall(f'.//{namespace}row'):
        values = {}
        for cell in row.findall(f'{namespace}c'):
            values[_xlsx_column_name(cell.attrib.get('r'))] = _xlsx_text(cell, shared_strings)
        if values:
            rows.append(values)
    return rows


def _parse_desired_number(raw_number, row_number):
    if raw_number in (None, ''):
        return DEFAULT_PURCHASE_NUMBER
    try:
        desired_number = int(float(str(raw_number).strip()))
    except ValueError as exc:
        raise ValueError(f"Invalid number on workbook row {row_number}: {raw_number!r}") from exc
    if desired_number < 1:
        raise ValueError(f"Workbook row {row_number} number must be 1 or greater.")
    return desired_number


def load_watch_items(path=WORKBOOK_PATH):
    workbook = ensure_private_workbook(path)
    rows = _worksheet_rows(workbook)
    if not rows:
        return []

    header_row = {column: value.strip().lower() for column, value in rows[0].items()}
    url_column = next((column for column, header in header_row.items() if header == 'url'), None)
    number_column = next((column for column, header in header_row.items() if header == 'number'), None)
    if not url_column or not number_column:
        raise ValueError("Workbook must contain columns named exactly: url, number")

    items = []
    for index, row in enumerate(rows[1:], start=2):
        url = row.get(url_column, '').strip()
        if not url:
            continue
        if not re.match(r'^https?://', url, re.I):
            raise ValueError(f"Workbook row {index} has an invalid url: {url!r}")
        desired_number = _parse_desired_number(row.get(number_column, ''), index)
        items.append(WatchItem(url=url, desired_number=desired_number))
    return items


def send_notifications(message):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={"Title": "SCURFA ALERT", "Priority": "urgent", "Tags": "watch"},
            timeout=10,
        )
        print("ntfy sent.")
    except Exception as e:
        print(f"ntfy failed: {e}")

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            requests.post(tg_url, json=payload, timeout=10)
            print("Telegram sent.")
        except Exception as e:
            print(f"Telegram failed: {e}")


def _is_enabled(tag):
    disabled = tag.get('disabled')
    aria_disabled = str(tag.get('aria-disabled', '')).lower()
    return disabled is None and aria_disabled != 'true'


def _extract_main_product_name(soup):
    heading = soup.select_one('div.single-product div.product h1.product_title, h1.product_title')
    if heading and heading.get_text(strip=True):
        return heading.get_text(strip=True)

    og_title = soup.find('meta', attrs={'property': 'og:title'})
    if og_title and og_title.get('content'):
        return og_title.get('content').strip()

    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return None


def _main_product_root(soup):
    return soup.select_one('div.single-product div.product') or soup.select_one('div.product')


def has_main_product_add_to_cart(soup):
    product_root = _main_product_root(soup)
    if not product_root:
        return False

    product_form = product_root.select_one('div.summary form.cart') or product_root.select_one('form.cart')
    if not product_form:
        return False

    add_to_cart_button = product_form.find(
        'button',
        attrs={
            'name': re.compile(r'add-to-cart', re.I),
            'class': re.compile(r'single_add_to_cart_button|add_to_cart_button', re.I),
        },
    )
    if add_to_cart_button and _is_enabled(add_to_cart_button):
        return True

    add_to_cart_input = product_form.find('input', attrs={'name': re.compile(r'add-to-cart', re.I)})
    submit_input = product_form.find('input', attrs={'type': re.compile(r'submit', re.I)})
    return bool(add_to_cart_input and submit_input and _is_enabled(submit_input))


def has_main_product_schema_in_stock(soup):
    main_name = _extract_main_product_name(soup)
    scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})

    for script in scripts:
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue

        text = raw.lower()
        if '"@type"' not in text or 'product' not in text:
            continue
        if main_name and main_name.lower() not in text:
            continue

        if 'instock' in text:
            return True
        if 'outofstock' in text:
            return False

    return None


def is_sold_out_in_main_product(soup):
    product_root = _main_product_root(soup)
    if not product_root:
        return False

    sold_out_phrases = [r'out of stock', r'sold out', r'awaiting stock', r'unavailable', r'backorder', r'not in stock']
    pattern = re.compile('|'.join(sold_out_phrases), re.I)
    return product_root.find(string=pattern) is not None


def _numeric_attribute(tag, attribute):
    raw_value = tag.get(attribute)
    if raw_value in (None, ''):
        return None
    try:
        value = int(float(str(raw_value)))
    except ValueError:
        return None
    return value if value > 0 else None


def available_quantity(soup):
    product_root = _main_product_root(soup)
    if not product_root:
        return None

    candidates = []
    for selector in ('input[name="quantity"]', '[data-max_quantity]', '[data-quantity]'):
        for tag in product_root.select(selector):
            for attribute in ('max', 'data-max_quantity', 'data-quantity'):
                value = _numeric_attribute(tag, attribute)
                if value is not None:
                    candidates.append(value)

    stock_text = ' '.join(product_root.stripped_strings)
    stock_patterns = [
        r'only\s+(\d+)\s+left',
        r'(\d+)\s+(?:in stock|available)',
        r'stock\s*[:\-]\s*(\d+)',
    ]
    for pattern in stock_patterns:
        match = re.search(pattern, stock_text, re.I)
        if match:
            candidates.append(int(match.group(1)))

    return min(candidates) if candidates else None


def purchase_quantity(desired_number, detected_available):
    if detected_available is None:
        return desired_number
    return min(desired_number, detected_available)


def _main_product_text_for_ai(soup, max_chars=2500):
    product_root = _main_product_root(soup)
    if not product_root:
        return ''

    # Keep content limited to avoid sending unrelated sections to AI.
    text = ' '.join(product_root.stripped_strings)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_chars]


def ai_availability_vote(soup):
    """Optional AI vote: returns True (in stock), False (out), or None (unknown/disabled)."""
    if not USE_AI_AVAILABILITY or not HF_TOKEN:
        return None

    context = _main_product_text_for_ai(soup)
    if not context:
        return None

    labels = ["in stock", "out of stock", "unknown"]
    payload = {
        "inputs": context,
        "parameters": {
            "candidate_labels": labels,
            "multi_label": False,
            "hypothesis_template": "This product is {}.",
        },
    }

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

    try:
        result = requests.post(url, headers=headers, json=payload, timeout=20)
        if result.status_code != 200:
            print(f"AI availability skipped (status={result.status_code}).")
            return None

        data = result.json()
        returned_labels = [label.lower() for label in data.get('labels', [])]
        returned_scores = data.get('scores', [])
        if not returned_labels or not returned_scores:
            return None

        top = returned_labels[0]
        top_score = float(returned_scores[0])
        if top_score < 0.60:
            return None
        if top == 'in stock':
            return True
        if top == 'out of stock':
            return False
        return None
    except Exception as e:
        print(f"AI availability skipped ({e}).")
        return None


def check_stock_for_item(item):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    time.sleep(random.randint(5, 30))

    try:
        response = requests.get(item.url, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"Error for {item.url}: Status code {response.status_code}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')

        schema_stock = has_main_product_schema_in_stock(soup)
        has_cart_form = has_main_product_add_to_cart(soup)
        sold_out_main = is_sold_out_in_main_product(soup)
        ai_vote = ai_availability_vote(soup)
        detected_available = available_quantity(soup)
        quantity_to_purchase = purchase_quantity(item.desired_number, detected_available)

        # Deterministic signals first; AI only complements when deterministic checks conflict/miss.
        in_stock = (schema_stock is True) or has_cart_form or (ai_vote is True and not sold_out_main)
        if in_stock and not sold_out_main:
            available_text = detected_available if detected_available is not None else 'unknown'
            msg = (
                f"🚨 *ITEM IN STOCK!* 🚨\n"
                f"Requested: {item.desired_number}\n"
                f"Detected available: {available_text}\n"
                f"Buy quantity: {quantity_to_purchase}\n"
                f"[Buy Now]({item.url})"
            )
            send_notifications(msg)
            return

        print(
            f"[{time.strftime('%H:%M:%S')}] Still awaiting stock for {item.url} "
            f"(requested={item.desired_number}, detected_available={detected_available}, "
            f"schema_stock={schema_stock}, product_cart_form={has_cart_form}, sold_out_main={sold_out_main}, ai_vote={ai_vote})."
        )

    except Exception as e:
        print(f"Check failed for {item.url}: {e}")


def check_stock():
    items = load_watch_items()
    if not items:
        print(f"No URLs configured. Add rows to {WORKBOOK_PATH} with columns: url, number.")
        return

    for item in items:
        check_stock_for_item(item)


if __name__ == "__main__":
    check_stock()
