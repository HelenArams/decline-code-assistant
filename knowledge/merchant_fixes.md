# Common merchant-side fixes

Most declines are the issuer's decision, but merchants control the data the
issuer sees and the way retries are performed. The fixes below are grouped by
the problem they address.

## Keep stored card data fresh

Stale credentials produce `54` (expired) and `14` (invalid number) on
subscriptions and card-on-file. Enrol in the schemes' account updater services
(Visa Account Updater, Mastercard Automatic Billing Updater) or, better, use
network tokens, which the issuer updates automatically when a card is
reissued. Run the updater before the billing run, not after the decline.

## Step up with 3-D Secure on soft declines

When the issuer returns `65` (Mastercard) or `1A` (Visa), authenticate the
cardholder with 3DS2 and resubmit the authorization with the cryptogram and
ECI. Build this as a single flow the customer experiences once, not as a
second checkout. Also apply 3DS2 proactively on first transactions of a
recurring agreement so later merchant-initiated transactions are exempt.

## Send complete authorization data

Issuers approve more when they can verify the cardholder. Always submit CVV2
for customer-present e-commerce, full AVS data where supported, a clear
descriptor, the correct MCC, and the right stored-credential and
merchant-initiated indicators. Missing or inconsistent data shows up as `05`,
`59`, and `N7`.

## Set stored-credential indicators correctly

Recurring, instalment, and unscheduled card-on-file transactions must carry
the initial-agreement reference and the correct indicators on each
authorization. Wrong indicators cause `12` (invalid transaction), `57`, and
issuer risk declines mapped to `05`. Schemes also fine merchants whose MIT
traffic is not flagged.

## Fix acquirer configuration before retrying

`03` and `58` are merchant setup problems: MCC not enabled for the channel,
currency not activated, MOTO or recurring not permitted on the MID. Open a
ticket with the acquirer with sample transaction references; retries will fail
until the configuration changes.

## Validate before you authorize

Run Luhn and BIN-range checks on the client to catch `14` and `15` before
sending; check expiry dates for `54`; enforce currency minor units to avoid
`13`. Each prevented authorization is a decline that never reaches the
issuer's view of the merchant.

## Respect hard declines

Never retry `04`, `41`, `43`, `14`, `R0`, `R1`, `59`. Block the credential for
the session or the subscription and ask for a different payment method. Hard
decline retries cost scheme fees and lower the issuer's trust in the merchant.

## Tune the dunning schedule

For subscriptions, retry `51` and `61` on a schedule aligned with salary dates
(1st, 15th, end of month), cap at four attempts in 30 days, and notify the
customer between attempts. Spread retries across the day rather than batching
them at midnight when issuer hosts run maintenance.

## Handle technical declines with backoff

`91` and `96` deserve one or two fast automated retries with a short backoff
(a few seconds, then a few minutes). If the rate stays elevated for more than a
few minutes, page the on-call engineer and check acquirer and scheme status
pages before touching the integration.

## Rate-limit card testing

Bursts of `14`, `N7`, `05` with many different PANs from a single IP, device,
or account are card-testing fraud. Add velocity limits per source, require
CAPTCHA or 3DS on suspicious sessions, and alert the fraud team rather than
treating it as a decline-rate problem.
