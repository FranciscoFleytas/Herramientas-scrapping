import json
import datetime
from test_bot import TestBot

URLS = [
    "https://www.instagram.com/p/DSz7ev-DTYr/",
    "https://www.instagram.com/p/DSz15G_jS2r/?img_index=1",
    "https://www.instagram.com/p/DSugvTBDcfB/?img_index=1",
    "https://www.instagram.com/p/DShzrTZDcI1/",
]

if __name__ == '__main__':
    bot = TestBot()
    results = []
    try:
        for u in URLS:
            print("\n==============================")
            print(f"Running for: {u}")
            res = bot.run_url(u, enable_save=False, dump_html_on_fail=True)
            results.append(res)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            # short pause between runs
            import time
            time.sleep(3)
    finally:
        bot.driver.quit()

    ts = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
    out_file = f"RESULTADOS/test_bot_results_{ts}.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved results to: {out_file}")
