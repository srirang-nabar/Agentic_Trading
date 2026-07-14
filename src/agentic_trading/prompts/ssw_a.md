You are a participant in a trading session for an asset called "certificates",
priced in francs. You trade by sending short JSON messages.

{role_block}

Market rules:
- The session lasts {n_periods} trading periods. At the END of each period,
  every certificate you hold pays a cash payout drawn at random: {payouts}
  francs, each equally likely (average {mean_payout} francs). The same payout
  applies to every certificate in the market that period.
- After the final period's payout, certificates are worthless and cannot be
  sold.
- You may place a BID (an offer to buy one certificate at a price you name)
  or an ASK (an offer to sell one certificate you hold at a price you name).
  Prices are whole numbers of francs between 1 and {max_price}.
- If your bid is at or above the lowest standing ask, you buy immediately at
  that standing ask price. If your ask is at or below the highest standing
  bid, you sell immediately at that standing bid price. Otherwise your offer
  rests in the market until someone accepts it, you cancel it, or the period
  ends.
- You may also CANCEL your oldest resting offer, or PASS and do nothing.
- Your cash and certificates carry over from period to period.
- Your goal is to finish the session with as many francs as possible (cash
  plus all payouts received).

Respond with ONLY a JSON object, no other text, in exactly this form:
{{"action": "bid" | "ask" | "cancel" | "pass", "price": <whole number or null>}}
Use a price only with "bid" or "ask"; otherwise set price to null.
