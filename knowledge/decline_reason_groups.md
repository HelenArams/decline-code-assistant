# Decline reason groups

Response codes are easier to act on when grouped by *who* declined and *why*.
The groups below are the ones a payments-ops team should slice a decline file
by before reading individual codes.

## Issuer declines

The cardholder's bank said no. These are the majority of declines and the
merchant has the least direct control over them. Sub-groups:

- **Account state** - insufficient funds (`51`), limits (`61`, `65`), card not
  activated (`78`). Temporary; retries work when timed well.
- **Card status** - expired (`54`), lost (`41`), stolen (`43`), pick-up (`04`),
  invalid number (`14`). Permanent for these credentials.
- **Card product restrictions** - not permitted to cardholder (`57`), restricted
  card (`62`). The product or the cardholder's settings block this use.
- **Risk and fraud** - suspected fraud (`59`), security violation (`63`), and a
  large share of generic `05`. Retries make the merchant look worse.
- **Cardholder verification** - PIN (`55`, `75`), CVV2 (`N7`), and the SCA soft
  declines (`65` on Mastercard, `1A` on Visa) that ask for 3-D Secure.
- **Recurring control** - stop-payment orders (`R0`, `R1`).

## Acquirer and processor declines

The merchant's own acquirer or gateway rejected the request before or after
the network. These are configuration or integration problems and are fixable
on the merchant side:

- Invalid merchant or terminal setup: `03`, `58`.
- Message defects: `12`, `13`, `30`.
- Duplicate detection: `94`.
- Gateway-level risk rules, velocity limits, or blocklists that are mapped onto
  `05` or `59` by the gateway. If the gateway exposes its own reason codes, read
  those first.

A sudden spike that affects *all* issuers at once is almost never the issuers;
look at the acquirer, the gateway, or a merchant release first.

## Network and switch declines

The scheme network could not complete the authorization:

- Issuer or switch down: `91`.
- Routing failures: `92`, `15`.
- Generic system errors: `96`.

These are technical, usually short-lived, and the only group where immediate
retries are appropriate. Watch for stand-in processing (the network approving on
the issuer's behalf) which can mask an issuer outage in the approval numbers.

## Soft versus hard declines

- A **soft decline** can succeed later or with different data: `51`, `61`, `65`,
  `1A`, `91`, `96`, and often `05`. Retry with a sensible schedule or step up
  authentication.
- A **hard decline** will not succeed with the same credentials: `04`, `14`,
  `41`, `43`, `54`, `57`, `59`, `62`, `R0`, `R1`. Stop, fix the data, or ask for
  a different card. Repeated attempts on hard declines trigger scheme reattempt
  fees and raise the merchant's fraud score with issuers.

## Diagnostic slicing

When a cluster of declines appears, slice it by:

1. **Response code** - the first cut; tells you soft/hard and the group above.
2. **Scheme** - a code may mean something slightly different on Visa versus
   Mastercard (`65` is the clearest example).
3. **Issuer BIN or country** - one issuer or one country means issuer rules; an
   even spread means merchant-side data or configuration.
4. **MCC and channel** - MCC-based blocks (`57`, `62`) and acquirer enablement
   (`03`, `58`) show up here.
5. **3-D Secure status** - unauthenticated EEA/UK traffic explains SCA soft
   declines and many `05`s.
6. **Retry count** - rows with high retry counts on hard declines are a
   compliance and cost problem, independent of the original reason.
