Melbet Payload Capture  —  Market + Bet
========================================

কী ধরে:
---------
1) Market feed (gameEvents)    → melbet_payloads/gameEvents_*.json
2) Wicket market changes       → melbet_payloads/WICKET_CHANGE_*.json
3) Bet request + response      → melbet_payloads/bets/BET_*.json        ⭐
4) Bet history (যদি কল হয়)    → melbet_payloads/bets/HISTORY_*.json
5) Summary                     → melbet_payloads/summary.log

চালানোর ধাপ:
------------
1) venv বানাও ও install:
       cd melbet-capture
       python -m venv .venv
       .venv\Scripts\Activate.ps1
       pip install -r requirements.txt

2) চালাও:
       python capture.py

3) ব্রাউজারে:
       a) Melbet-এ লগইন করো
       b) একটি লাইভ ম্যাচ খোলো
       c) ২-৫ over কাটতে দাও (market feed হবে)
       d) ছোট (১৫-২০) stake-এ ১-২টি bet ধরো
          ✅ বিশেষত "Fall of Xth Wicket" market-এ
       e) ১-২টি wicket পড়তে দাও
       f) Ctrl+C — থামাও

⚠️ এগুলো real bet — টাকা যাবে। ছোট stake-এ ধরো।

কীভাবে বুঝবে কোনটা কী:
-------------------------
files/timestamps দেখে:
  - gameEvents_*.json     → প্রতি ২ সেকেন্ডে market snapshot
  - WICKET_CHANGE_*.json  → wicket-এ market বদলালে
  - BET_*.json            → যখন bet ধরেছ
  - HISTORY_*.json        → Melbet নিজে bet-history কল করলে

কোন ফাইলগুলো আমাকে পাঠাবে (wicket_worker ঠিক করতে):
----------------------------------------------------
1) ২টি BET_*.json — যেগুলো Wicket market-এ ধরেছ
   (একটি সফল, একটি fail হলে আরও ভালো)
2) ২-৩টি WICKET_CHANGE_*.json
3) ১টি gameEvents_*.json — একটি wicket-এর আগে
4) ১টি gameEvents_*.json — ওই wicket-এর পরে
5) summary.log (শুধু প্রথম ৫০ লাইন)

নিরাপত্তা:
-----------
- Cookie, Authorization, X-Auth-Token header স্বয়ংক্রিয়ভাবে "***REDACTED***" হবে
- শুধু request body (Type/Param/Coef/Summ) দৃশ্যমান — যেটা debug-এ দরকার

Profile:
---------
profile/ ফোল্ডারে Melbet login session থাকবে।
পরেরবার চালালে লগইন লাগবে না।

বন্ধ:
-----
Ctrl+C। আবার চালালে বাকি কাজ থেকে শুরু।