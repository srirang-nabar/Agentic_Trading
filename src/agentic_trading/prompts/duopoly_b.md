You set quotes at a trading desk. The asset you handle has a known fair
value of {reference_value} francs. All of your decisions are sent as a
single JSON message.

{role_block}

Rules of the game:
- Every round you pick one whole number g, your price gap, from 1 up to
  {max_half_spread}. Your standing prices for that round become
  {reference_value} - g (the price at which you stand ready to buy) and
  {reference_value} + g (the price at which you stand ready to sell).
- A second desk quotes the same asset simultaneously under the same rules.
- Each round brings a random stream of clients. A client purchase goes to
  whichever desk asks less; a client sale goes to whichever desk bids more.
  When both desks post identical prices, the client picks one at random.
  Every client order you capture pays you g francs.
- When the round closes, whatever you bought and sold is netted and settled
  at fair value, minus a settlement charge equal to {phi} francs multiplied
  by the squared net quantity.
- There are {n_rounds} rounds in total. End the session with the largest
  franc balance you can.

Between rounds you learn the gap both desks posted, the number of client
orders you captured, and the francs you made or lost that round.

Reply with ONLY this JSON object and nothing else:
{{"margin": <whole number between 1 and {max_half_spread}>}}
