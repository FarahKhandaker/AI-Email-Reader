"""Classifies emails using regex patterns"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .models import Category, Classification, Email, Priority

log = logging.getLogger("classifier")

# All the regex patterns, one per category.
# The order of if-checks in _rule_classify() does matter — receipts need to go
# first or they'll get flagged as payment issues.

RECEIPT_PATTERNS = re.compile(
    r"\b("
    r"paid successfully|payment (received|successful|confirmed)|receipt|"
    r"no action (is )?(required|needed)|thank you for your payment|"
    r"order (confirmed|received|placed)|booking confirmed|reservation confirmed|"
    r"your order (has shipped|is on its way|has been delivered|was delivered)|"
    r"out for delivery|successfully delivered|shipment (confirmed|dispatched)|"
    r"auto.?renewal (successful|complete)|subscription renewed successfully|"
    r"transaction (complete|successful)|purchase (complete|successful|confirmed)|"
    r"you'?re all set|successfully subscribed|welcome aboard"
    r")\b",
    re.IGNORECASE,
)

PAYMENT_PATTERNS = re.compile(
    r"\b("
    r"payment (failed|unsuccessful|declined|rejected|could not be processed)|"
    r"failed .*(payment|charge|transaction)|"
    r"charged twice|double charge|duplicate (charge|payment)|"
    r"card .*(declined|failed|rejected|expired|expiring|will expire|about to expire)|"
    r"credit card (expiring|expired|expiry|invalid)|"
    r"refund|chargeback|dispute(d)? (charge|payment|transaction)|"
    r"billing (issue|problem|error|failed|failure)|"
    r"overcharg(ed|e)|"
    r"invoice .*(unpaid|overdue|failed|past due)|"
    r"(outstanding|unpaid|overdue) (balance|invoice|amount)|"
    r"amount (due|past due|overdue)|past due balance|"
    r"insufficient funds|payment (not received|missing)|"
    r"failed to (renew|charge|process)|renewal (failed|unsuccessful)|"
    r"auto.?renewal (failed|unsuccessful|canceled)|"
    r"subscription (canceled|cancelled|terminated) (due to|because of) (payment|billing|non.?payment)|"
    r"unable to (process|complete) (your )?(payment|charge|transaction)|"
    r"could not (charge|process|bill)|"
    r"trial (ending|ends|expir|about to end)|free trial (end|expir)|"
    r"upgrade (required|needed|your plan)|payment (plan|arrangement) (issue|problem)"
    r")\b",
    re.IGNORECASE,
)

SERVER_PATTERNS = re.compile(
    r"\b("
    r"outage|503|502|500 error|404 error|"
    r"not responding|unreachable|down\b|timed? out|"
    r"incident|error rate|degraded( service)?|service disruption|system failure|"
    r"(api|production|prod|server|service|system|infrastructure|platform|backend|frontend|app|application|website|site|database|db|cluster|node|pod|container|worker|queue|job|cron|pipeline|ci|cd|deploy)"
    r" .*(down|outage|issue|problem|failure|error|unreachable|not responding|crashed?|unavailable|offline|unresponsive|degraded)|"
    r"high (cpu|memory|load|traffic|latency|error rate)|"
    r"(cpu|memory|disk|ram) (usage|utilization|pressure|full|exhausted|limit)|"
    r"out of (memory|disk( space)?)|disk (full|space|usage)|OOM|"
    r"health.?check (fail|down|error|alert)|endpoint (down|fail|unreachable)|"
    r"ssl (certificate|cert) (expir|invalid|error|fail)|certificate (expir|invalid|revoked|error)|tls error|"
    r"(db|database) (connection|error|down|fail|crash|unreachable|timeout)|"
    r"connection (timeout|refused|reset|failed|error|dropped)|"
    r"latency (spike|high|alert|issue)|slow (response|query|request)|response time (high|degraded|alert)|"
    r"(job|task|worker|cron|build|deploy|pipeline|sync|backup|replication|webhook|integration) (fail|crash|error|stuck|hung|timeout|abort)|"
    r"deploy(ment)? (fail|error|abort|rollback)|rollback (triggered|required|initiated)|"
    r"unhandled exception|stack trace|traceback|panic:|segmentation fault|null pointer|"
    r"alert (fired|triggered)|pagerduty|alertmanager|grafana alert|datadog alert|new relic|"
    r"replication lag|replica (behind|failing)|backup (fail|missing|incomplete)|"
    r"rate limit (hit|exceeded|reached)|throttl(ed|ing)|api (limit|quota) (hit|exceeded|reached)|"
    r"webhook (fail|error|timeout)|integration (fail|error|broken)|sync (fail|error)|"
    r"queue (backed up|overflow|full|stuck)|message (backlog|lag|stuck)"
    r")\b",
    re.IGNORECASE,
)

COMPLAINT_PATTERNS = re.compile(
    r"\b("
    r"disappointed|frustrated|unacceptable|"
    r"cancel(ling|ing|ed|)? my (account|subscription|service|plan|membership)|"
    r"complaint|angry|furious|livid|outraged|"
    r"terrible|worst|horrible|awful|dreadful|"
    r"broken for (days|weeks|months)|nobody (responds|helps|answers|cares)|"
    r"escalate|escalation|"
    r"this is ridiculous|this is a joke|completely (broken|useless|unacceptable)|"
    r"(want|demand|requesting|expect) (a |my )?(full )?refund|money back|"
    r"will (sue|take legal action|contact my lawyer|file a complaint)|"
    r"legal action|lawsuit|lawyer|attorney|"
    r"better business bureau|\bBBB\b|filing a complaint|"
    r"leaving (a )?(review|1.star|one.star|bad review|negative review)|"
    r"contacted (my bank|my credit card)|disputed the charge|initiating (a )?chargeback|"
    r"going (public|to (social media|twitter|reddit|press))|tell (everyone|all my friends)|"
    r"waste of money|rip.?off|\bscam\b|fraudulent (service|product|company)|"
    r"(weeks|months) of (issues|problems|bugs)|no (support|response|help)|"
    r"never (works|worked|fixed)|always (fails|broken|down)|"
    r"switching to (a )?competitor|moving to|canceling everything|done with (your|this)"
    r")\b",
    re.IGNORECASE,
)

SECURITY_PATTERNS = re.compile(
    r"\b("
    r"security (alert|incident|breach|issue|event|warning|notice|threat)|"
    r"new sign.?in|sign.?in (from|on) (new|unknown|unrecognized)|"
    r"suspicious (activity|login|sign.?in|access|request|email)|"
    r"unauthorized (access|login|sign.?in|activity|change|transaction)|"
    r"compromised|account (breach|hacked|hijacked)|"
    r"2fa|two.factor|verify your (account|identity|email|phone)|"
    r"unusual (activity|login|sign.?in|access)|"
    r"anomalous (activity|behavior|access)|"
    r"data (breach|leak|leakage|exposure|exposed|stolen|compromised)|"
    r"(api key|secret|token|credential|password|private key) (exposed|leaked|compromised|stolen|found online)|"
    r"vulnerability|CVE.?\d|zero.?day|security patch|critical patch|"
    r"phishing|malware|ransomware|virus (detected|found)|spyware|trojan|"
    r"(brute force|ddos|sql injection|\bxss\b|injection attack|man.in.the.middle) (attack|detected|attempt)|"
    r"account (locked|suspended|blocked|disabled) .{0,30}(attempt|login|sign.?in|suspicious)|"
    r"too many (failed|incorrect) (login|sign.?in|password) attempt|"
    r"password (reset|change) request(ed)?|"
    r"session (hijack|stolen|expired unexpectedly)|"
    r"(penetration test|pentest) (finding|result|report)|"
    r"firewall (breach|alert|blocked)|intrusion (detected|attempt|alert)"
    r")\b",
    re.IGNORECASE,
)

URGENT_PATTERNS = re.compile(
    r"\b("
    r"urgent|asap|immediately|emergency|right away|"
    r"need .{0,20} today|"
    r"can'?t wait|time[- ]sensitive|time.critical|"
    r"deadline|due (today|tomorrow|this (morning|afternoon|evening))|"
    r"by (end of day|EOD|COB|close of business|end of week|EOW|tonight|this (friday|monday|tuesday|wednesday|thursday))|"
    r"expires? (today|tonight|in \d+ hours?)|expiring (now|soon|today)|"
    r"last chance|final (notice|warning|reminder|call)|"
    r"pending (your )?approval|awaiting (your )?approval|needs? your approval|please approve|"
    r"action required|response (needed|required|requested)|please respond|your (response|reply|input|feedback) is (needed|required)|"
    r"(waiting|blocked|blocking) on you|waiting for (your )?response|"
    r"\bcritical\b|\bblocker\b|show.stopper|"
    r"at your earliest (convenience)?|as soon as possible|"
    r"overdue .{0,30}(report|task|deliverable|item)|"
    r"cannot (proceed|continue|move forward) without"
    r")\b",
    re.IGNORECASE,
)

SPAM_PATTERNS = re.compile(
    r"("
    r"%|\bsale\b|\bdiscount\b|\b\d+% off\b|limited stock|click now|claim your|"
    r"\bwinner\b|act now|\bfree\b|unsubscribe|🔥|!!!|biggest sale|"
    r"you'?ve been selected|you'?re a winner|you'?ve won|congratulations! you|dear (winner|friend|customer),|"
    r"earn (money|cash|income)|make money|passive income|work from home|"
    r"click here to (claim|get|download|access)|claim (your prize|your reward|now)|"
    r"100% free|no (obligation|credit card required|strings attached)|risk.?free offer|"
    r"money.back guarantee|satisfaction guaranteed|"
    r"lose weight|weight loss|diet (pill|supplement|plan)|fat (burn|loss)|"
    r"casino|\bjackpot\b|\blottery\b|\bpoker\b|\bslot machine\b|"
    r"bitcoin investment|crypto (gains|profits|opportunity)|nft (drop|sale|mint)|get rich|"
    r"(meet|hot|local) singles|dating (site|app)|"
    r"increase (your sales|traffic|followers|revenue) (fast|instantly|overnight)|"
    r"double your (money|income|traffic)|boost your (ranking|sales|income) (fast|instantly)|"
    r"limited.time offer|offer (ends|expires) (tonight|midnight|soon)|"
    r"dear (valued )?(customer|member|user),|"
    r"you have (been|been) (pre.?approved|selected|chosen)|"
    r"(buy|order) now and (get|receive|save)"
    r")",
    re.IGNORECASE,
)

SUBSCRIPTION_PATTERNS = re.compile(
    r"\b("
    r"newsletter|weekly digest|daily digest|monthly (update|newsletter|report|roundup)|"
    r"quarterly (report|update|newsletter)|annual (report|summary|review)|"
    r"you appeared in|profile views|"
    r"recommended for you|your weekly|"
    r"\bpremium\b .{0,20}(feature|plan|tier|offer)|"
    r"unsubscribe (at any time|from this|below)|manage (your )?(preferences|notifications|subscriptions)|"
    r"you'?re receiving this (because|email|newsletter)|why am i getting this|"
    r"opt.out|email (preferences|settings)|"
    r"this is an automated (message|email|notification)|do not (reply|respond) to this (email|message)|"
    r"liked your (post|photo|comment|tweet)|commented on (your|a)|mentioned you|"
    r"new (follower|connection|friend request)|someone (viewed|visited) your profile|"
    r"connection request|people you may know|"
    r"app update (available|released)|new version (available|released)|"
    r"terms of service (update|change)|privacy policy (update|change)|we'?ve updated our (terms|policy|privacy)|"
    r"scheduled maintenance|planned maintenance|maintenance (window|notice)|"
    r"(your )?(monthly|weekly|annual) (statement|account summary|usage report|activity (summary|report))|"
    r"invitation to (webinar|workshop|event|seminar)|webinar (reminder|registration)|"
    r"(take a |please complete (our |the )?)survey|we'?d love your feedback .{0,30}(unsubscribe|no.reply)|"
    r"you'?re (now )?subscribed|subscription (confirmation|confirmed)|"
    r"digest|roundup|recap|highlights from|top stories|"
    r"(google|facebook|twitter|instagram|linkedin|slack|github|jira|trello) (notification|alert|summary|digest)"
    r")\b",
    re.IGNORECASE,
)

NOISE_SENDERS = re.compile(
    r"("
    r"no.?reply|do.?not.?reply|"
    r"newsletter|notifications?@|promotions?@|"
    r"linkedin@|e\.linkedin|"
    r"marketing@|digest@|"
    r"automated@|system@|mailer@|mailer.daemon|"
    r"bounce@|postmaster@|"
    r"updates?@.*(google|facebook|twitter|instagram|github|slack|jira|trello|shopify|stripe|paypal|amazon|ebay)|"
    r"team@.*(substack|mailchimp|hubspot|sendgrid|klaviyo)"
    r")",
    re.IGNORECASE,
)


@dataclass
class _RuleHit:
    important: bool
    priority: Priority
    category: Category
    reason: str


def _rule_classify(email: Email) -> _RuleHit:
    text = f"{email.subject}\n{email.body}"
    sender = email.from_

    # Check receipts first — they need to win over payment issue patterns
    if RECEIPT_PATTERNS.search(text):
        log.debug("hit receipt pattern: %r", email.subject)
        return _RuleHit(False, Priority.LOW, Category.SUBSCRIPTION,
                        "Looks like a receipt or confirmation, no action needed.")

    if PAYMENT_PATTERNS.search(text):
        log.debug("looks like a payment issue: %r", email.subject)
        return _RuleHit(True, Priority.HIGH, Category.PAYMENT_ISSUE,
                        "Payment or billing problem — failed charge, expired card, refund, or overdue invoice.")
    if SERVER_PATTERNS.search(text):
        log.debug("server/infra alert detected: %r", email.subject)
        return _RuleHit(True, Priority.HIGH, Category.SERVER_DOWN,
                        "Looks like a production outage or service degradation that needs attention now.")
    if COMPLAINT_PATTERNS.search(text):
        log.debug("customer complaint detected: %r", email.subject)
        return _RuleHit(True, Priority.HIGH, Category.CLIENT_COMPLAINT,
                        "Angry customer — strong negative sentiment, churn threat, or legal escalation.")
    if SECURITY_PATTERNS.search(text):
        log.debug("security alert detected: %r", email.subject)
        return _RuleHit(True, Priority.HIGH, Category.SECURITY_ALERT,
                        "Security event — unknown sign-in, data breach, credential leak, or vulnerability report.")

    if URGENT_PATTERNS.search(text):
        log.debug("urgent request detected: %r", email.subject)
        return _RuleHit(True, Priority.MEDIUM, Category.URGENT_REQUEST,
                        "Sender is flagging this as urgent or time-sensitive.")

    if SPAM_PATTERNS.search(text):
        log.debug("spam detected: %r", email.subject)
        return _RuleHit(False, Priority.LOW, Category.SPAM,
                        "Looks like marketing spam or a bulk promotional email.")
    if SUBSCRIPTION_PATTERNS.search(text) or NOISE_SENDERS.search(sender):
        log.debug("subscription/newsletter email: %r", email.subject)
        return _RuleHit(False, Priority.LOW, Category.SUBSCRIPTION,
                        "Automated newsletter, digest, or social notification — no action needed.")

    log.debug("no pattern matched, treating as general: %r", email.subject)
    return _RuleHit(True, Priority.MEDIUM, Category.GENERAL,
                    "Doesn't match any noise pattern, so probably worth a look.")


def classify(email: Email) -> Classification:
    rule = _rule_classify(email)
    log.info("classified email — priority=%s  category=%s  important=%s  subject=%r",
             rule.priority.value, rule.category.value, rule.important, email.subject)
    return Classification(
        important=rule.important,
        priority=rule.priority,
        category=rule.category,
        reason=rule.reason,
        classified_by="rules",
    )
