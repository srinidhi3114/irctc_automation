from playwright.sync_api import sync_playwright
import pandas as pd
import calendar

def wait_for_overlays_to_disappear(page):
    print(" Waiting for overlays to disappear...")

    try:
        page.wait_for_selector(".ui-dialog-mask", state="hidden", timeout=15000)
        print(" Modal dialog mask removed.")
    except:
        print(" Modal mask still present. Proceeding cautiously...")

    if page.locator(".captcha-img").is_visible():
        print(" CAPTCHA is present. Manual input required. Exiting.")
        page.screenshot(path="captcha_blocked.png")
        return False

    page.evaluate("""
        () => {
            const iframe = document.querySelector("iframe[id^='google_ads_iframe']");
            if (iframe) {
                iframe.style.display = 'none';
            }
        }
    """)
    print(" Hidden advertisement iframe (if found).")
    return True

def click_date_input(page):
    selectors = [
        "input[placeholder='Journey Date']",
        "input[aria-label='Journey Date']",
        "input[placeholder*='Date']",
        "input[type='text']"
    ]
    for sel in selectors:
        try:
            locator = page.locator(sel)
            count = locator.count()
            if count == 0:
                continue
            if sel == "input[type='text']" and count >= 3:
                locator = locator.nth(2)
            locator.wait_for(state="visible", timeout=10000)
            locator.click()
            print(f"Clicked date input with selector: {sel}")
            return True
        except Exception as e:
            print(f"Failed with selector '{sel}': {e}")
            continue

    print("Could not find or click Journey Date input field.")
    return False

def select_journey_date(page, dd, mm, yyyy):
    target_month_name = calendar.month_name[mm][:3].lower()
    go_next = page.locator("a.ui-datepicker-next")
    max_clicks = 13

    while max_clicks > 0:
        found = False
        titles = page.locator(".ui-datepicker-title")
        count = titles.count()
        for i in range(count):
            title = titles.nth(i).inner_text().strip()
            if str(yyyy) in title and target_month_name in title.lower():
                found = True
                break
        if found:
            break
        go_next.click()
        page.wait_for_timeout(300)
        max_clicks -= 1

    day_btns = page.locator(f".ui-datepicker-calendar td a:text-is('{dd}')")
    for i in range(day_btns.count()):
        if day_btns.nth(i).is_visible():
            day_btns.nth(i).click()
            page.wait_for_timeout(500)
            print(f" Journey Date selected: {dd:02d}/{mm:02d}/{yyyy}")
            return

    raise Exception("Could not find the day button in the calendar.")

def scrape_irctc_trains():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context()
        page = context.new_page()

        try:
            print(" Opening IRCTC website...")
            url = "https://www.irctc.co.in/nget/train-search"
            print(f" Navigating to {url}...")
            page.goto(url, timeout=120000, wait_until="load")
            print(" IRCTC page loaded successfully.")

            print(" Checking for Aadhaar popup...")
            try:
                page.wait_for_timeout(3000)
                popup_ok = page.locator("//button[text()='OK']")
                popup_ok.wait_for(state="visible", timeout=10000)
                popup_ok.click()
                print(" Aadhaar popup dismissed.")
            except:
                print(" No Aadhaar popup found. Proceeding.")

            all_inputs = page.locator("input[type='text']")
            from_input = all_inputs.nth(0)
            from_input.click()
            from_input.fill("MAS")
            page.wait_for_timeout(1000)
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
            print(" Filled 'From' station: MAS")

            print(" Clearing overlays before filling 'To' station...")
            if not wait_for_overlays_to_disappear(page):
                print(" Cannot proceed due to CAPTCHA.")
                return

            inputs = page.locator("input[role='searchbox']")
            print(f" Found {inputs.count()} search boxes")
            to_input = inputs.nth(1)
            to_input.click()
            to_input.fill("SBC")
            page.wait_for_timeout(1000)
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
            print(" 'To' station filled: SBC")

            print(" Selecting Journey Date using calendar widget...")
            if not click_date_input(page):
                raise Exception("Journey Date input field not found or not clickable.")
            select_journey_date(page, 26, 7, 2025)
            print(" Journey Date entered.")

            print(" Clicking 'Find trains'...")
            page.click("button:has-text('Search')")
            print(" Waiting up to 12 seconds for train results to appear...")
            page.wait_for_timeout(12000)
            page.screenshot(path="after_search_click.png", full_page=True)

            print(" Waiting for AJAX loader spinner to disappear...")
            try:
                page.wait_for_selector("div.loader-block", timeout=8000)
                page.wait_for_selector("div.loader-block", timeout=60000, state="hidden")
                print(" Loader disappeared.")
            except:
                print(" No loader/spinner found, proceeding...")

            print(" Waiting for train list to load...")
            selectors = [
                "div[class*='available-train-block']",
                "div[class*='train-avl-enq-block']",
                "div.available-train-block",
                "div.train-avl-enq-block"
            ]
            trains = None
            count = 0
            for sel in selectors:
                try:
                    page.wait_for_selector(sel, timeout=10000)
                    trains = page.locator(sel)
                    count = trains.count()
                    if count > 0:
                        print(f" Found {count} trains with selector: {sel}")
                        break
                except:
                    continue

            if not trains or count == 0:
                print("No trains found with tested selectors.")
                page.screenshot(path="error_train_list_not_found.png", full_page=True)
                with open("error_train_list_not_found.html", "w", encoding="utf-8") as f:
                    f.write(page.content())

                print("\n Dumping sample <div> texts to inspect structure:")
                divs = page.locator("div")
                lim = min(divs.count(), 15)
                for i in range(lim):
                    text = divs.nth(i).inner_text().strip()
                    if text:
                        print(f"Div {i}: {text[:120]}")

                full_text = page.inner_text("body")
                print("\n Full page visible text:\n", full_text[:1000])
                return

            print(f" Found {count} trains. Scraping...")

            train_data = []
            for i in range(count):
                try:
                    block = trains.nth(i)
                    name = block.locator("div.train-heading span").nth(0).inner_text(timeout=10000)
                    number = block.locator("div.train-heading span").nth(1).inner_text(timeout=10000)
                    dep_time = block.locator("div[class*='time-info'] span").nth(0).inner_text(timeout=10000)
                    arr_time = block.locator("div[class*='time-info'] span").nth(1).inner_text(timeout=10000)

                    train_data.append({
                        "Train Name": name.strip(),
                        "Train Number": number.strip(),
                        "Departure Time": dep_time.strip(),
                        "Arrival Time": arr_time.strip()
                    })
                except Exception as e:
                    print(f" Skipping train {i+1}: {e}")
                    continue

            if train_data:
                df = pd.DataFrame(train_data)
                df.to_csv("irctc_trains.csv", index=False)
                print(" Train data saved to 'irctc_trains.csv'")
            else:
                print(" No train data extracted.")

        except Exception as e:
            print(f" Unexpected error occurred: {e}")
            page.screenshot(path="unexpected_error.png", full_page=True)

        finally:
            print(" Closing browser...")
            browser.close()

if __name__ == "__main__":
    scrape_irctc_trains()
