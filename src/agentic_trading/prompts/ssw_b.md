You are taking part in an exchange where traders buy and sell "coupons".
All amounts are in francs. You act by returning a single JSON message.

{role_block}

How the exchange works:
- Trading happens over {n_periods} rounds. When a round closes, each coupon
  in your possession earns a return, decided by chance for that round: it is
  {payouts} francs, all outcomes equally probable (the long-run average is
  {mean_payout} francs per coupon). Every coupon in the market earns the same
  return in a given round.
- Once the last round's return has been paid, coupons expire with zero value
  and trading in them stops.
- To buy, submit a BID stating the price you would pay for one coupon. To
  sell a coupon you own, submit an ASK stating the price you would accept.
  Only whole-franc prices from 1 to {max_price} are allowed.
- A bid that meets or beats the cheapest open ask trades at once, at that
  ask's price. An ask that meets or beats the highest open bid trades at
  once, at that bid's price. Any other offer stays open until it is matched,
  withdrawn, or the round closes.
- Instead of quoting, you may CANCEL your oldest open offer, or PASS this
  turn.
- Francs and coupons are not reset between rounds; whatever you hold carries
  forward.
- Aim to end the session holding the largest possible total of francs,
  counting both your cash and every return paid to you.

Reply with ONLY this JSON object and nothing else:
{{"action": "bid" | "ask" | "cancel" | "pass", "price": <whole number or null>}}
Give a price only for "bid" or "ask"; use null otherwise.
