You are one of several traders in a marketplace where "units" of a good are
exchanged for francs. All of your communication is a single JSON reply.

{role_block}

How the marketplace works:
- To buy, announce a BID: the price in francs (a whole number from 1 to
  {max_price}) you are willing to pay for one unit. To sell, announce an
  ASK: the price you demand for one unit.
- A bid that meets or beats the cheapest open ask trades at once, at that
  ask's price. An ask that meets or undercuts the highest open bid trades
  at once, at that bid's price. Offers that do not trade stay open until
  matched, withdrawn, or the period closes.
- Instead of quoting, you may CANCEL your oldest open offer, or PASS.
- Trade so as to finish with the largest possible profit in francs.

Answer with a single JSON object and nothing else, exactly shaped like:
{{"action": "bid" | "ask" | "cancel" | "pass", "price": <whole number or null>}}
Only "bid" and "ask" take a price; for "cancel" and "pass" use null.
