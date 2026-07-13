import re
import json
from bs4 import BeautifulSoup

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

with open("scratch/dom.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")

data = {}

# Product ID
main_div = soup.select_one(".product-info-main")
data["product_id"] = main_div.get("data-product-id") if main_div else ""

# Title
title_elem = soup.select_one(".page-title .base")
data["title"] = clean(title_elem.get_text()) if title_elem else ""

# Subtitle
subtitle_elem = soup.select_one(".product-subtitle span")
data["subtitle"] = clean(subtitle_elem.get_text()) if subtitle_elem else ""

# Stock Status
stock_elem = soup.select_one(".stock.available span")
data["stock_status"] = clean(stock_elem.get_text()) if stock_elem else ""

# Availability qty warning
qty_warning_elem = soup.select_one(".configurable-variation-qty")
data["stock_warning"] = clean(qty_warning_elem.get_text()) if qty_warning_elem else ""

# SKU
sku_elem = soup.select_one(".product.attribute.sku .value")
data["sku"] = clean(sku_elem.get_text()) if sku_elem else ""

# Prices
# Find final price
final_price_elem = soup.select_one(".price-final_price #product-price-" + (data["product_id"] or ""))
if not final_price_elem:
    final_price_elem = soup.select_one("[id^=product-price-]")
data["price"] = clean(final_price_elem.get_text()) if final_price_elem else ""

# MRP
mrp_elem = soup.select_one(".price-final_price #old-price-" + (data["product_id"] or ""))
if not mrp_elem:
    mrp_elem = soup.select_one("[id^=old-price-]")
data["old_price"] = clean(mrp_elem.get_text()) if mrp_elem else ""

# Discount
discount_elem = soup.select_one(".price-discount .price")
data["discount"] = clean(discount_elem.get_text()) if discount_elem else ""

# Meta details for price
price_meta = soup.select_one("meta[itemprop='price']")
data["price_amount"] = price_meta.get("content") if price_meta else ""
currency_meta = soup.select_one("meta[itemprop='priceCurrency']")
data["price_currency"] = currency_meta.get("content") if currency_meta else ""

# Reviews
review_elem = soup.select_one(".product-reviews-summary a.action.add")
data["reviews_text"] = clean(review_elem.get_text()) if review_elem else ""
data["reviews_link"] = review_elem.get("href") if review_elem else ""

# Net Quantity
manufactured_by_elem = soup.select_one(".product.attribute.manufactured_by")
net_qty = ""
if manufactured_by_elem:
    # Look for "Net Quantity :"
    for span in manufactured_by_elem.find_all("span"):
        if "Net Quantity" in span.get_text():
            # Get sibling or subsequent element
            bold_sibling = span.find_next("span", class_="bold")
            if bold_sibling:
                net_qty = clean(bold_sibling.get_text())
                break
data["net_quantity"] = net_qty

# Key Features
key_features = []
features_wrapper = soup.select_one("#customShortDescription")
if features_wrapper:
    for li in features_wrapper.select("ul li"):
        key_features.append(clean(li.get_text()))
data["key_features"] = key_features

# Swatches / Color Options
colors = {}
swatch_attr = soup.select_one(".swatch-attribute.color")
if swatch_attr:
    label = swatch_attr.select_one(".swatch-attribute-label")
    selected_option = swatch_attr.select_one(".swatch-attribute-selected-option")
    colors["attribute_name"] = clean(label.get_text()) if label else "Colour"
    colors["selected"] = clean(selected_option.get_text()) if selected_option else ""
    
    options = []
    for opt in swatch_attr.select(".swatch-option.color"):
        opt_data = {
            "id": opt.get("data-option-id"),
            "label": opt.get("data-option-label"),
            "tooltip": opt.get("data-option-tooltip-value"),
            "style": opt.get("style")
        }
        options.append(opt_data)
    colors["options"] = options
data["color_options"] = colors

# Installation
installation = {}
inst_section = soup.select_one(".pruduct_installation_section")
if inst_section:
    title_elem = inst_section.select_one(".title")
    desc_elem = inst_section.select_one(".desc")
    installation["title"] = clean(title_elem.get_text()) if title_elem else ""
    installation["description"] = clean(desc_elem.get_text()) if desc_elem else ""
    
    sku_val = inst_section.select_one("#installation-product-sku-value")
    inst_type = inst_section.select_one("[id^=installation_][id$=type]") # wait, id installation_FHCNME5MBN48-c class installation_type
    if not inst_type:
        inst_type = inst_section.select_one(".installation_type")
    inst_price = inst_section.select_one("[id^=installation_price_]")
    inst_msg = inst_section.select_one("[id^=installationTextMessage_]")
    
    installation["sku"] = sku_val.get("value") if sku_val else ""
    installation["type"] = inst_type.get("value") if inst_type else ""
    installation["price"] = inst_price.get("value") if inst_price else ""
    installation["success_message"] = inst_msg.get("value") if inst_msg else ""
data["installation"] = installation

# Offers
offers = []
offers_section = soup.select_one("#applicableOffers")
if offers_section:
    for col in offers_section.select(".col-6, .mb-4.col-6, .mb-4"):
        # Check if it has offer details
        p_tag = col.select_one("p")
        if not p_tag:
            continue
        offer_text = clean(p_tag.get_text())
        a_tag = col.select_one("a")
        offer_link = a_tag.get("href") if a_tag else ""
        
        # Check for loyalty token
        token_elem = p_tag.select_one("#loyalty_amounts_eligible")
        tokens = clean(token_elem.get_text()) if token_elem else ""
        
        title = "Loyalty Offer" if tokens else "App Offer"
        
        offers.append({
            "title": title,
            "text": offer_text,
            "tokens_eligible": tokens,
            "link": offer_link
        })
data["offers"] = offers

# Total Price
total_price_elem = soup.select_one(".product-total-price .total-price-by-qty .price")
data["total_price"] = clean(total_price_elem.get_text()) if total_price_elem else ""

print(json.dumps(data, indent=2))
