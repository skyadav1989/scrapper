
# Updated scraper.py (partial enhanced version)

from idna import idnadata
from idna import idnadata
from idna import idnadata
from idna import idnadata
from asyncio import subprocess
from idna import idnadata
import os
import re
import json
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

CATEGORY = "home-appliances"
CSV_FILE="output/havells_"+CATEGORY+".csv"
OUTPUT_DIR="output/products/"+CATEGORY
BATCH_SIZE=10
os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean(t):
    return re.sub(r"\s+"," ", t or "").strip()

def scrape_product(page, product_url):
    page.goto(product_url, wait_until="networkidle")
    page.wait_for_timeout(3000)
    soup=BeautifulSoup(page.content(),"lxml")

    

    data={
        "url":product_url,
        "product_id":"",
        "title":"",
        "subtitle":"",
        "category":"",
        "sku":"",
        "stock_status":"",
        "stock_warning":"",
        "price":"",
        "old_price":"",
        "discount":"",
        "price_amount":"",
        "price_currency":"",
        "key_features":[],
        "variations":{},
        "installation":{},
        "warranty_options":[],
        "offers":[],
        "total_price":"",
        "description":"",
        "specifications":{},
        "technical_specifications" : {},
        "images":[]
    }

    for s in soup.select("script[type='application/ld+json']"):
        try:
            obj=json.loads(s.string)
            objs=obj if isinstance(obj,list) else [obj]
            for item in objs:
                if item.get("@type")=="Product":
                    data["title"]=item.get("name","") or data["title"]
                    data["description"]=item.get("description","")
                    data["sku"]=item.get("sku","") or data["sku"]
                    off=item.get("offers",{})
                    if isinstance(off,dict):
                        data["price_amount"]=str(off.get("price",""))
                        data["price_currency"]=off.get("priceCurrency","")
                        av=off.get("availability","")
                        if av:
                            data["stock_status"]=av.split("/")[-1]
                    imgs=item.get("image",[])
                    if isinstance(imgs,list):
                        data["images"].extend(imgs)
        except Exception:
            pass

    pid=soup.select_one("input[name=product]")
    if pid: data["product_id"]=pid.get("value","")
    

    h1=soup.select_one("h1")
    if h1: data["title"]=clean(h1.get_text())

    sub = soup.select_one(".product-subtitle")
    if sub: data["subtitle"] = clean(sub.get_text())

    breadcrumbs = soup.select(".breadcrumbs .items li")

    categories = []

    for item in breadcrumbs:
        # Skip Home and Product
        if "home" in item.get("class", []) or "product" in item.get("class", []):
            continue

        text = item.get_text(strip=True)
        if text:
            categories.append(text)

    data["category"] = " > ".join(categories)

    sku=soup.select_one("[itemprop='sku']")
    if sku: data["sku"]=clean(sku.get_text())

    stock=soup.select_one(".stock.available,.stock")
    if stock: data["stock_status"]=clean(stock.get_text())

    price=soup.select_one("[id^='product-price-']")
    if price: data["price"]=clean(price.get_text())

    old=soup.select_one(".old-price .price")
    if old: data["old_price"]=clean(old.get_text())

    desc=soup.select_one(".product.attribute.description")
    if desc: data["description"]=clean(desc.get_text())

    for li in soup.select(".product.attribute.overview li,.key-features li,.feature-list li"):
        t=clean(li.get_text())
        if t: data["key_features"].append(t)

    specs={}
    for tr in soup.select("table tr"):
        td=tr.find_all(["th","td"])
        if len(td)>=2:
            specs[clean(td[0].get_text())]=clean(td[1].get_text())
    data["specifications"]=specs

    # ----------------------------------
    # Technical Specifications
    # ----------------------------------

    technical_specs = {}

    section = soup.select_one("#technicalSpecsSection")

    if section:

        for row in section.select(".specs-row"):

            label = row.select_one(".data-label")
            value = row.select_one(".data-value")

            if not label or not value:
                continue

            key = clean(label.get_text())

            # Join all spans so units like "1200 mm" become one value
            val = " ".join(
                clean(span.get_text())
                for span in value.select("span")
                if clean(span.get_text())
            )

            if not val:
                val = clean(value.get_text())

            technical_specs[key] = val

    data["technical_specifications"] = technical_specs

    variations = []

    wrapper = soup.select_one("#product-options-wrapper")

    if wrapper:
        for attr in wrapper.select(".swatch-attribute"):
            label = attr.select_one(".swatch-attribute-label")
            if not label:
                continue

            options = []
            for opt in attr.select(".swatch-option"):
                value = opt.get("data-option-label")
                if value and value not in options:
                    options.append(value.strip())

            variations.append({
                "name": clean(label.get_text()),
                "options": options
            })

    data["variations"] = variations

    gallery=[]
    for img in soup.select("img.fotorama__img,img.gallery-image"):
        src=img.get("src") or img.get("data-src") or img.get("data-full") or img.get("data-lazy")
        if not src:
            continue
        if src.startswith("//"): src="https:"+src
        elif src.startswith("/"): src="https://havells.com"+src
        if src not in gallery:
            gallery.append(src)
    data["images"]=gallery or data["images"]

    sku=data["sku"] or re.sub(r"[^A-Za-z0-9]","_",product_url.split("/")[-1])
    file_path = os.path.join(OUTPUT_DIR, f"{sku}.json")

    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved: {file_path}")
    else:
        print(f"Skipped (already exists): {file_path}")

def main():
    df=pd.read_csv(CSV_FILE)
    col=next((c for c in df.columns if "url" in c.lower()),None)
    if not col:
        raise RuntimeError("No URL column found.")
    urls=df[col].dropna().astype(str).unique().tolist()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page()
        for i in range(0,len(urls),BATCH_SIZE):
            for url in urls[i:i+BATCH_SIZE]:
                try:
                    scrape_product(page,url)
                except Exception as e:
                    print("FAILED",url,e)
        browser.close()

if __name__=="__main__":
    main()
