-- Simplified GA4 default channel grouping from session source/medium.
-- The obfuscated sample replaces some values with '<Other>' or '(data deleted)';
-- those get their own bucket so they are measured instead of hidden.
CREATE OR REPLACE MACRO channel_group(src, med) AS
  CASE
    WHEN src IS NULL AND med IS NULL                                   THEN 'Unassigned'
    WHEN src IN ('<Other>', '(data deleted)')
      OR med IN ('<Other>', '(data deleted)')                          THEN 'Obfuscated'
    WHEN src = '(direct)' AND coalesce(med, '(none)') IN ('(none)', '(not set)') THEN 'Direct'
    WHEN lower(med) = 'organic'                                        THEN 'Organic Search'
    WHEN lower(med) IN ('cpc', 'ppc', 'paidsearch')                    THEN 'Paid Search'
    WHEN lower(med) IN ('display', 'cpm', 'banner')                    THEN 'Display'
    WHEN lower(med) IN ('email', 'e-mail', 'e_mail')                   THEN 'Email'
    WHEN lower(med) = 'affiliate'                                      THEN 'Affiliates'
    WHEN lower(med) = 'referral'                                       THEN 'Referral'
    ELSE 'Other'
  END;
