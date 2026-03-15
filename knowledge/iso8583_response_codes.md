# ISO 8583 response codes (DE 39)

Field 39 of an ISO 8583 authorization response carries a two-character response
code. `00` is an approval; almost everything else is a decline or an error. The
code tells you *who* said no (issuer, acquirer, or network) and roughly *why*,
but issuers map their internal reasons onto these codes inconsistently, so a
code is a strong hint, not a proof. Each entry below records the usual meaning,
whether the decline is soft (temporary) or hard (permanent for these
credentials), and whether a retry makes sense.

Format of each entry:

- **Group** - who produced the decline and the broad reason family.
- **Kind** - `soft` (may succeed later or with different data), `hard` (do not
  retry with the same credentials), `technical` (infrastructure, retry quickly).
- **Retryable** - whether and when an automated reattempt is acceptable.
- **Severity** - operational urgency for a payments team seeing a spike.

## 00 - Approved

- **Group:** approval
- **Kind:** n/a
- **Retryable:** n/a
- **Severity:** none

The authorization was approved. A row with `00` in a decline file is a data
quality problem in the export, not a decline; flag it rather than explaining it.

## 01 - Refer to card issuer

- **Group:** issuer / referral
- **Kind:** soft
- **Retryable:** no (automated); the cardholder should contact the issuer
- **Severity:** low

The issuer wants a voice referral or a cardholder call before approving. Online
merchants cannot act on a referral, so treat it like `05` and ask the customer
to contact their bank or use another card. Do not loop retries.

## 03 - Invalid merchant

- **Group:** acquirer / configuration
- **Kind:** hard (for this merchant setup)
- **Retryable:** no until the configuration is fixed
- **Severity:** high

The merchant ID, terminal ID, or MCC is not recognised or not enabled for this
transaction type at the acquirer or issuer. A burst of `03` right after a
configuration change or a new MID rollout almost always points to acquirer
onboarding, not to cardholders. Check MID/TID, MCC, enabled currencies, and
whether the acquirer has activated the merchant for card-not-present traffic.

## 04 - Pick up card

- **Group:** issuer / card status
- **Kind:** hard
- **Retryable:** never
- **Severity:** medium (fraud signal)

The issuer has flagged the card (lost, stolen, or closed for cause). Never
retry. In card-present this means capture the card; online it means block the
credential for this customer and review the account for account-takeover
signals.

## 05 - Do not honor

- **Group:** issuer / generic
- **Kind:** hard for the current attempt, often soft over days
- **Retryable:** at most one reattempt after 24-72 hours, unless the issuer
  pattern indicates a fraud rule
- **Severity:** medium

The catch-all issuer decline. It hides many real reasons: a risk rule, a
suspected-fraud model score, a blocked merchant category, a card not activated
for e-commerce, or an issuer that does not expose granular codes. Diagnose by
slicing: if `05` concentrates on one issuer BIN, one MCC, or one country, the
issuer's risk rules are the likely cause. If it is spread evenly, look at the
merchant's own data quality (descriptor, AVS/CVV submission, 3DS usage).
Reattempting repeatedly with the same data looks like testing and attracts
scheme reattempt fees.

## 12 - Invalid transaction

- **Group:** issuer or acquirer / message format
- **Kind:** hard (for this message)
- **Retryable:** no until the request is fixed
- **Severity:** high

The transaction type is not valid for this card or terminal, or a mandatory
field combination is wrong (for example a refund without an original, a
pre-authorisation on a card product that does not support it, or an MIT
without a valid stored-credential indicator). Treat a spike as an integration
regression and compare request payloads before and after the deploy.

## 13 - Invalid amount

- **Group:** issuer or acquirer / message format
- **Kind:** hard (for this message)
- **Retryable:** no until the amount is fixed
- **Severity:** high

The amount is zero, negative, exceeds the field length, has the wrong minor
unit for the currency, or is above the product's maximum. Check currency
exponents (JPY has 0 decimals, KWD has 3) and tip/incremental amount handling.

## 14 - Invalid card number

- **Group:** issuer / card data
- **Kind:** hard
- **Retryable:** never with the same PAN
- **Severity:** medium

The PAN fails the Luhn check, the BIN does not exist, or the account is unknown
to the issuer. Online this is usually a typo or a closed account. Validate Luhn
on the client, use an account updater or network tokens for stored cards, and
never retry the same number.

## 15 - No such issuer

- **Group:** network / routing
- **Kind:** hard
- **Retryable:** never with the same PAN
- **Severity:** low

The BIN does not map to any issuer. Almost always an invalid or fabricated card
number. Treat like `14`.

## 30 - Format error

- **Group:** acquirer or network / message format
- **Kind:** technical
- **Retryable:** no until the message is fixed
- **Severity:** high

The ISO message itself is malformed: wrong bitmap, bad field length, invalid
encoding. This is a merchant or gateway integration defect. Diff the raw
message against the spec and look at recent gateway releases.

## 41 - Lost card

- **Group:** issuer / card status
- **Kind:** hard
- **Retryable:** never
- **Severity:** medium (fraud signal)

The card was reported lost. Never retry; block the credential.

## 43 - Stolen card

- **Group:** issuer / card status
- **Kind:** hard
- **Retryable:** never
- **Severity:** medium (fraud signal)

The card was reported stolen. Never retry; block the credential and review the
customer account for compromise indicators.

## 51 - Insufficient funds

- **Group:** issuer / account balance
- **Kind:** soft
- **Retryable:** yes - wait at least 24 hours; schedule retries around likely
  payday (1st, 15th, end of month) and stop after four attempts in 30 days
- **Severity:** low

The most common decline worldwide. The account lacks funds or available credit
for the amount. This is genuinely temporary, so a well-timed retry recovers a
large share. Do not split the amount into smaller charges to get around it;
schemes classify that as circumventing the decline. For subscriptions, retry on
a dunning schedule and tell the customer.

## 54 - Expired card

- **Group:** issuer / card data
- **Kind:** hard (for this expiry date)
- **Retryable:** only after the expiry date is updated
- **Severity:** low

The expiry date is past or does not match the issuer's record. Reattempting
with the same date is pointless. For stored credentials, run an account updater
request or use network tokens so the new expiry arrives automatically; for
one-off checkout, ask the customer to re-enter the date.

## 55 - Incorrect PIN

- **Group:** issuer / cardholder verification
- **Kind:** soft
- **Retryable:** cardholder may re-enter; see `75` for the limit
- **Severity:** low

The offline or online PIN did not verify. Card-present only in practice. After
the issuer's limit the card returns `75`.

## 57 - Transaction not permitted to cardholder

- **Group:** issuer / card product restriction
- **Kind:** hard
- **Retryable:** no with the same card
- **Severity:** medium

The card product does not allow this kind of transaction: e-commerce disabled,
cross-border blocked, gambling or crypto MCC blocked, recurring not permitted
on a prepaid product. A cluster of `57` on one MCC usually means the issuer
blocks that category. Ask the customer to enable online or international
payments in their banking app or use a different card.

## 58 - Transaction not permitted to terminal

- **Group:** acquirer / merchant configuration
- **Kind:** hard (for this merchant setup)
- **Retryable:** no until the configuration is fixed
- **Severity:** high

The acquirer does not allow this transaction type for the merchant: MCC not
enabled for MOTO or recurring, currency not enabled, refunds disabled. Like
`03`, a spike after a configuration change points at the acquirer setup.

## 59 - Suspected fraud

- **Group:** issuer / risk
- **Kind:** hard
- **Retryable:** no
- **Severity:** high

The issuer's fraud model declined the authorization. Do not retry; a retry
looks like a fraudster probing. Improve the data the issuer sees: send full
AVS and CVV, use 3-D Secure so the issuer gets authenticated transactions, and
make sure the descriptor and MCC describe the business honestly.

## 61 - Exceeds withdrawal amount limit

- **Group:** issuer / limits
- **Kind:** soft
- **Retryable:** yes, after the limit window resets (typically next day)
- **Severity:** low

The amount pushes the card over its daily, weekly, or per-transaction limit.
Retry the next day or ask the cardholder to raise the limit. Do not split the
amount to sneak under the limit.

## 62 - Restricted card

- **Group:** issuer / card restriction
- **Kind:** hard
- **Retryable:** no with the same card
- **Severity:** medium

The card is restricted for this use: geo-blocked for the merchant's country,
limited to domestic use, or restricted to specific MCCs (for example fuel or
corporate travel cards). Clusters of `62` on cross-border traffic are the
classic signature.

## 63 - Security violation

- **Group:** issuer / security
- **Kind:** hard
- **Retryable:** no
- **Severity:** high

A cryptographic or security check failed: bad ARQC, CVV mismatch on some
issuers, or a card flagged for compromise. Treat as a fraud signal and inspect
the cryptogram and CVV data path for defects.

## 65 - Exceeds withdrawal frequency limit / authentication required

- **Group:** issuer / limits, or issuer / soft decline for SCA
- **Kind:** soft
- **Retryable:** yes - after the window resets, or immediately with 3-D Secure
  authentication when used as an SCA soft decline
- **Severity:** medium

Historically "too many transactions in the period". Under PSD2 Strong Customer
Authentication, Mastercard issuers return `65` as a *soft decline* meaning
"authenticate the cardholder and resubmit". Visa issuers use `1A` for the same
purpose. If `65` clusters on EEA/UK cards without a 3-D Secure result, the fix
is to step up through 3DS2 and resubmit with the authentication data, not to
wait.

## 75 - Allowable number of PIN tries exceeded

- **Group:** issuer / cardholder verification
- **Kind:** hard (until the issuer resets)
- **Retryable:** no
- **Severity:** low

The cardholder exhausted PIN attempts; the card is blocked until the issuer
unblocks it. Card-present only.

## 78 - Blocked, first used

- **Group:** issuer / card status
- **Kind:** hard (until activated)
- **Retryable:** after the cardholder activates the card
- **Severity:** low

A newly issued card has not been activated. Ask the cardholder to activate it
and try again.

## 91 - Issuer or switch inoperative

- **Group:** network / technical
- **Kind:** technical
- **Retryable:** yes - once after a short backoff, then a second attempt a few
  minutes later; stop if the issuer is still down
- **Severity:** high when clustered

The issuer host or the network switch did not respond. A short burst on one BIN
is an issuer outage; a burst across all issuers is the acquirer or network.
This is the one decline where an immediate automated retry is both acceptable
and effective. Stand-in processing may approve some of these at the network.

## 92 - Unable to route transaction

- **Group:** network / routing
- **Kind:** technical
- **Retryable:** no until routing is fixed
- **Severity:** high

The network could not find a destination for the BIN. Usually a new BIN range
not yet loaded at the acquirer, or an unsupported scheme on this route.

## 94 - Duplicate transmission

- **Group:** acquirer or network / idempotency
- **Kind:** technical
- **Retryable:** no - look up the original result instead
- **Severity:** medium

The same STAN/RRN was seen already. The original probably succeeded; query it
before doing anything else. A spike indicates a client retrying without
changing the trace number.

## 96 - System malfunction

- **Group:** issuer or network / technical
- **Kind:** technical
- **Retryable:** yes - after a short backoff, limited attempts
- **Severity:** high when clustered

A generic system error on the issuer or network side. Treat like `91`: retry a
couple of times with backoff, then alert if the rate stays elevated.

## 1A - Additional customer authentication required

- **Group:** issuer / soft decline for SCA (Visa)
- **Kind:** soft
- **Retryable:** yes - immediately after 3-D Secure authentication
- **Severity:** medium

Visa's soft decline for PSD2 Strong Customer Authentication. The issuer wants
the cardholder authenticated. Step up through 3DS2, then resubmit the
authorization with the CAVV/AAV and ECI. Mastercard uses `65` for the same.

## N7 - CVV2 failure

- **Group:** issuer / card verification
- **Kind:** hard (for this CVV)
- **Retryable:** no with the same CVV
- **Severity:** medium

The security code did not match. Often a typo at checkout; sometimes
card-testing fraud when it clusters on many PANs from one source. Ask the
customer to re-enter; rate-limit sources producing many `N7`s.

## R0 / R1 - Stop payment or revocation of authorisation order

- **Group:** issuer / recurring
- **Kind:** hard
- **Retryable:** never
- **Severity:** medium

The cardholder told the issuer to stop a specific recurring payment (`R0`) or
all recurring payments to this merchant (`R1`). Cancel the subscription and
tell the customer. Retrying is a scheme violation.
