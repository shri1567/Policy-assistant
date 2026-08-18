# Information Security Policy

**Document ID:** POL-004
**Version:** 4.1
**Effective Date:** 2026-02-01
**Status:** Active

## Section 1 — Purpose and Scope
This policy defines minimum security requirements for protecting company and client data across all employees, contractors, and systems. It applies regardless of whether an employee is working from an office, home, or while traveling, and takes precedence over convenience when the two conflict.

## Section 2 — Password and Authentication
2.1 All company accounts must use multi-factor authentication (MFA) where technically available, using either an authenticator app or hardware token; SMS-based MFA is permitted only as a fallback where no other option exists.
2.2 Passwords must be at least 12 characters, changed every 180 days, and must not be reused across the last 5 passwords. Passwords must combine upper case, lower case, numbers, and at least one symbol.
2.3 Shared or generic accounts (e.g., team mailboxes) are discouraged; where unavoidable, they must have a designated owner and a password rotation logged with IT every 90 days.

## Section 3 — Data Classification
3.1 Data is classified into four tiers: Public, Internal, Confidential, and Restricted. Classification should be applied at the point of creation and re-evaluated if the data's sensitivity changes.
3.2 Restricted data (e.g., client PII, financial records, health information) must never be stored on personal devices or personal cloud storage, and must not be emailed to personal addresses under any circumstance.
3.3 Confidential data may be stored on company-managed devices only, with encryption at rest enabled; it may be shared externally only through approved secure-transfer tools, not standard email attachments.
3.4 Internal data may be shared within the company freely but should not be posted to public or external-facing platforms without a classification review.

## Section 4 — Device Security
4.1 All company laptops must have disk encryption, endpoint detection software, and automatic screen lock after 5 minutes of inactivity. These controls are enforced centrally by IT and cannot be disabled by the end user.
4.2 Personal devices used for email access (BYOD) must be enrolled in the mobile device management (MDM) system, which allows the company to remotely wipe corporate data (not personal data) if the device is lost or the employee exits.
4.3 USB storage devices are disabled by default on company laptops; exceptions require a documented business reason and IT approval, logged with an expiry date.

## Section 5 — Incident Reporting
5.1 Any suspected security incident (phishing, data leak, lost device, unauthorized access) must be reported to the Security team within 1 hour of discovery, via the dedicated incident hotline or security@company email.
5.2 Failure to report a known incident within 24 hours is treated as a policy violation subject to disciplinary review, regardless of whether the incident ultimately caused harm.
5.3 The Security team will acknowledge receipt of a report within 2 hours during business hours and provide an initial assessment within 1 business day.

## Section 6 — Third-Party and AI Tools
6.1 Confidential or Restricted data must not be entered into unapproved third-party AI tools or public generative AI services, including for tasks like summarization or translation.
6.2 Only AI tools listed on the Approved Tools Registry may be used for work involving company data; the registry is maintained by the Security team and reviewed quarterly.
6.3 New third-party tool requests (AI or otherwise) that would process company data must go through a vendor security review before adoption, even for free or trial tiers.

## Section 7 — Exceptions
7.1 Security exceptions (e.g., use of an unapproved tool for a time-boxed pilot) require sign-off from the CISO and must be logged in the Exception Register with an expiry date, after which the exception automatically lapses unless renewed.
7.2 Exceptions involving Restricted data require an additional Legal review before approval, given regulatory and contractual implications.
