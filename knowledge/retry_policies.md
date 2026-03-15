# Retry policies

Schemes now police reattempts: Visa and Mastercard both charge fees and can
levy compliance penalties for excessive or forbidden reattempts of declined
authorizations. A retry policy therefore has to be code-aware, not just
"try again tomorrow".

## Scheme reattempt rules in brief

- **Visa** groups declines into categories. Category 1 ("issuer will never
  approve": lost, stolen, pick-up, invalid account, and similar) must not be
  reattempted at all. Category 2 ("issuer cannot approve at this time":
  insufficient funds, limits, do-not-honor) and category 3 ("data quality":
  expired, bad CVV2, invalid data) allow at most 15 reattempts in 30 days, and
  category 3 expects the data to be fixed first.
- **Mastercard** similarly defines declines that must not be reattempted and
  caps other reattempts at 10 per 24 hours for the same card and merchant.
- Both schemes treat splitting an amount or changing the amount to evade a
  decline as a violation.

Treat these as the ceiling; the recommended schedules below are well inside
them.

## Do not retry (hard declines)

`04`, `41`, `43`, `14`, `15`, `59`, `63`, `R0`, `R1`, and `57`/`62` for the same
card and merchant. Block the credential, request another payment method, and
for recurring agreements cancel or pause the subscription.

## Retry with a schedule (soft account-state declines)

- `51` insufficient funds: wait at least 24 hours; retry near likely payday;
  at most four attempts in 30 days.
- `61` amount limit, `65` frequency limit (non-SCA meaning): retry after the
  issuer's limit window, typically the next calendar day; two attempts.
- `05` do not honor: at most one reattempt after 24-72 hours. If `05` is the
  issuer's response to a risk rule, a second attempt rarely helps and the
  customer should be asked for another card.
- `78` not activated: retry only after the customer confirms activation.

## Retry after fixing the data (data-quality declines)

- `54` expired card: update the expiry via account updater or the customer,
  then retry once.
- `N7` CVV2 failure, `13` invalid amount, `12` invalid transaction, `30`
  format error: do not retry until the data or the message is corrected.

## Retry immediately with authentication (SCA soft declines)

- `65` on Mastercard and `1A` on Visa: perform 3DS2 authentication and resubmit
  immediately with the cryptogram and ECI. This is not counted as a reattempt
  of the same transaction when authentication data changes.

## Retry fast with backoff (technical declines)

- `91` issuer or switch inoperative, `96` system malfunction: retry after a
  few seconds, then after a few minutes, maximum three attempts. Stop and alert
  if the failure rate stays elevated.
- `94` duplicate transmission: do not retry; query the original transaction
  and reconcile.

## Retry-count hygiene

A `retry_count` higher than one on any hard decline is a policy violation
regardless of the original reason. A `retry_count` above four on `51` or above
three on `91` indicates a runaway retry loop. These rows deserve a finding of
their own even when the underlying decline reason is benign.
