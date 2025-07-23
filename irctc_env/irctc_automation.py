from playwright.sync_api import sync_playwright
import pandas as pd

def scrape_irctc_trains():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context()
        page = context.new_page()

        print("🚀 Opening IRCTC website...")
        page.goto("https://www.irctc.co.in/nget/train-search")

        # ✅ Wait for the page to fully load and inputs to become visible
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        # ✅ Wait for From* input to be visible and handle popup
        from_input = page.locator("input[placeholder='From*']")
        from_input.wait_for(state="visible", timeout=10000)
        page.keyboard.press("Escape")
        page.wait_for_timeout(1000)

        print("🔍 Entering From Station...")
        from_input.click()
        from_input.fill("chennai central")
        page.keyboard.press("Enter")

        print("🔍 Entering To Station...")
        to_input = page.locator("input[placeholder='To*']")
        to_input.click()
        to_input.fill("bangalore")
        page.keyboard.press("Enter")

        print("📅 Selecting Journey Date...")
        date_input = page.locator("input[placeholder='Journey Date*']")
        date_input.click()
        page.keyboard.press("Enter")  # Select today's date

        print("🔎 Clicking Find Trains...")
        page.click("button:has-text('Find trains')")
        page.wait_for_timeout(8000)

        print("⏳ Waiting for train list to load...")
        try:
            page.wait_for_selector("div.train_avl_enq_box", timeout=10000)
        except:
            print("❌ No trains found or page did not load.")
            page.screenshot(path="irctc_debug.png")
            browser.close()
            return

        trains = page.locator("div.train_avl_enq_box")
        count = trains.count()
        print(f"📋 Found {count} trains. Scraping...")

        train_data = []

        for i in range(count):
            try:
                block = trains.nth(i)
                name = block.locator(".col-sm-5 span").nth(0).inner_text()
                number = block.locator(".col-sm-5 span").nth(1).inner_text()
                dep_time = block.locator(".col-sm-3 span").nth(0).inner_text()
                arr_time = block.locator(".col-sm-3 span").nth(1).inner_text()

                train_data.append({
                    "Train Name": name,
                    "Train Number": number,
                    "Departure Time": dep_time,
                    "Arrival Time": arr_time
                })
            except Exception as e:
                print(f"⚠️ Skipping row {i}: {e}")
                continue

        browser.close()

    if train_data:
        df = pd.DataFrame(train_data)
        df.to_csv("irctc_trains.csv", index=False)
        print("✅ Train data saved to 'irctc_trains.csv'")
    else:
        print("❌ No train data extracted.")

if __name__ == "__main__":
    scrape_irctc_trains()






