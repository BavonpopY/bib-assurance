-- =====================================================================
--  BIB Assurance (Bangkok Insurance & Benefits)
--  "Trusted Protection for Every Stage of Life"
--  Script 2 of 3 : 02_routines.sql
--  Programmable objects (Slides 6-8, Lab 8, Lab 9, Lab 14):
--    * 7 Functions    fn_...
--    * 18 Triggers    trg_...   (SIGNAL SQLSTATE '45000' rejects bad data)
--    * 9 Views        vw_...
--    * 15 Procedures  sp_...    (START TRANSACTION / COMMIT / ROLLBACK)
--  Safe to re-run: every object is dropped first.
--
--  NOTE on binary logging: MySQL 8 has log_bin ON by default, so every
--  function declares DETERMINISTIC or READS SQL DATA (otherwise error 1418).
--  NOTE on SIGNAL: MESSAGE_TEXT is limited to 128 characters.
-- =====================================================================

USE bibdb;

-- =====================================================================
-- PART A : FUNCTIONS (Lab 9.2 - CREATE FUNCTION ... RETURNS ...)
-- =====================================================================

-- A1) Age in whole years on a reference date (pass CURDATE() for "today")
DROP FUNCTION IF EXISTS fn_age;
DELIMITER $$
CREATE FUNCTION fn_age(
  p_dob DATE,
  p_ref_date DATE
)
RETURNS INT
DETERMINISTIC
BEGIN
  RETURN TIMESTAMPDIFF(YEAR, p_dob, p_ref_date);
END $$
DELIMITER ;

-- A2) Pretty document numbers: BIB-2026-000123 / CLM-2026-000045
DROP FUNCTION IF EXISTS fn_format_number;
DELIMITER $$
CREATE FUNCTION fn_format_number(
  p_prefix VARCHAR(5),
  p_id INT,
  p_date DATE
)
RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
  RETURN CONCAT(p_prefix, '-', YEAR(p_date), '-', LPAD(p_id, 6, '0'));
END $$
DELIMITER ;

-- A3) Rating multiplier lookup: product override first, then global default
DROP FUNCTION IF EXISTS fn_get_multiplier;
DELIMITER $$
CREATE FUNCTION fn_get_multiplier(
  p_product_id INT,
  p_factor_type VARCHAR(10),
  p_value INT
)
RETURNS DECIMAL(5,3)
READS SQL DATA
BEGIN
  DECLARE v_multiplier DECIMAL(5,3);
  SET v_multiplier = (SELECT multiplier
                      FROM premium_factor
                      WHERE factor_type = p_factor_type
                        AND p_value BETWEEN range_min AND range_max
                        AND (product_id = p_product_id OR product_id IS NULL)
                      ORDER BY (product_id IS NULL), factor_id
                      LIMIT 1);
  RETURN IFNULL(v_multiplier, 1.000);
END $$
DELIMITER ;

-- A4) Label for the same lookup ("Standard", "Age 40-59", "Occupation class 2", ...)
DROP FUNCTION IF EXISTS fn_factor_label;
DELIMITER $$
CREATE FUNCTION fn_factor_label(
  p_product_id INT,
  p_factor_type VARCHAR(10),
  p_value INT
)
RETURNS VARCHAR(60)
READS SQL DATA
BEGIN
  DECLARE v_label VARCHAR(60);
  SET v_label = (SELECT label
                 FROM premium_factor
                 WHERE factor_type = p_factor_type
                   AND p_value BETWEEN range_min AND range_max
                   AND (product_id = p_product_id OR product_id IS NULL)
                 ORDER BY (product_id IS NULL), factor_id
                 LIMIT 1);
  RETURN IFNULL(v_label, 'Standard');
END $$
DELIMITER ;

-- A5) THE DYNAMIC PREMIUM CALCULATOR (Module 2)
--     premium = base_annual_premium x (coverage / min_coverage)
--               x age multiplier x risk multiplier x (duration_months / 12)
--     Multiply first, divide once at the end -> no rounding drift.
--     Returns NULL when the inputs are outside the tier's rules.
DROP FUNCTION IF EXISTS fn_calc_premium;
DELIMITER $$
CREATE FUNCTION fn_calc_premium(
  p_tier_id INT,
  p_age INT,
  p_risk_level INT,
  p_coverage DECIMAL(12,2)
)
RETURNS DECIMAL(10,2)
READS SQL DATA
BEGIN
  DECLARE v_product_id INT;
  DECLARE v_base DECIMAL(10,2);
  DECLARE v_min DECIMAL(12,2);
  DECLARE v_max DECIMAL(12,2);
  DECLARE v_months INT;
  DECLARE v_premium DECIMAL(20,6);
  DECLARE v_found INT DEFAULT 1;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_found = 0;

  SELECT product_id, base_annual_premium, min_coverage, max_coverage, duration_months
    INTO v_product_id, v_base, v_min, v_max, v_months
    FROM coverage_tier
    WHERE tier_id = p_tier_id;

  IF v_found = 0 OR p_coverage IS NULL OR p_age IS NULL OR p_risk_level IS NULL THEN
    RETURN NULL;
  ELSEIF p_coverage < v_min OR p_coverage > v_max OR p_age < 18 OR p_risk_level NOT BETWEEN 1 AND 4 THEN
    RETURN NULL;
  END IF;

  SET v_premium = (v_base * p_coverage
                   * fn_get_multiplier(v_product_id, 'AGE', p_age)
                   * fn_get_multiplier(v_product_id, 'RISK', p_risk_level)
                   * v_months)
                  / (v_min * 12);
  RETURN ROUND(v_premium, 2);
END $$
DELIMITER ;

-- A6) Live policy status for any date (used by views, triggers, procedures)
DROP FUNCTION IF EXISTS fn_policy_live_status;
DELIMITER $$
CREATE FUNCTION fn_policy_live_status(
  p_status VARCHAR(20),
  p_start DATE,
  p_end DATE,
  p_remaining DECIMAL(12,2),
  p_ref_date DATE
)
RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
  RETURN CASE
           WHEN p_status = 'Cancelled' THEN 'Cancelled'
           WHEN p_ref_date > p_end     THEN 'Expired'
           WHEN p_remaining <= 0       THEN 'Exhausted'
           WHEN p_ref_date < p_start   THEN 'Scheduled'
           ELSE 'Active'
         END;
END $$
DELIMITER ;

-- A7) Total beneficiary allocation of a policy (0.00 - 100.00)
DROP FUNCTION IF EXISTS fn_beneficiary_total;
DELIMITER $$
CREATE FUNCTION fn_beneficiary_total(
  p_policy_id INT
)
RETURNS DECIMAL(6,2)
READS SQL DATA
BEGIN
  RETURN (SELECT IFNULL(SUM(allocation_pct), 0.00)
          FROM policy_beneficiary
          WHERE policy_id = p_policy_id);
END $$
DELIMITER ;


-- =====================================================================
-- PART B : TRIGGERS (Lab 9.2 - BEFORE/AFTER INSERT/UPDATE/DELETE, FOLLOWS)
-- =====================================================================

-- B1) app_user : lower-case e-mail, customers must give a DOB and be 18+
DROP TRIGGER IF EXISTS trg_app_user_before_insert;
DELIMITER $$
CREATE TRIGGER trg_app_user_before_insert
  BEFORE INSERT ON app_user
  FOR EACH ROW
BEGIN
  DECLARE v_role_code VARCHAR(20);
  SET NEW.email = LOWER(TRIM(NEW.email));
  SET v_role_code = (SELECT role_code FROM role WHERE role_id = NEW.role_id);
  IF v_role_code = 'CUSTOMER' THEN
    IF NEW.date_of_birth IS NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Customers must provide a date of birth.';
    ELSEIF fn_age(NEW.date_of_birth, CURDATE()) < 18 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Applicants must be at least 18 years old to purchase a policy.';
    END IF;
  END IF;
END $$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_app_user_before_update;
DELIMITER $$
CREATE TRIGGER trg_app_user_before_update
  BEFORE UPDATE ON app_user
  FOR EACH ROW
BEGIN
  DECLARE v_role_code VARCHAR(20);
  SET NEW.email = LOWER(TRIM(NEW.email));
  SET v_role_code = (SELECT role_code FROM role WHERE role_id = NEW.role_id);
  IF v_role_code = 'CUSTOMER' THEN
    IF NEW.date_of_birth IS NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Customers must provide a date of birth.';
    ELSEIF fn_age(NEW.date_of_birth, CURDATE()) < 18 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Customers must be at least 18 years old.';
    END IF;
  END IF;
END $$
DELIMITER ;

-- B2) policy : full coverage on day one, coverage within tier range,
--     only customers own policies, status calculated automatically
DROP TRIGGER IF EXISTS trg_policy_before_insert;
DELIMITER $$
CREATE TRIGGER trg_policy_before_insert
  BEFORE INSERT ON policy
  FOR EACH ROW
BEGIN
  DECLARE v_min DECIMAL(12,2);
  DECLARE v_max DECIMAL(12,2);
  DECLARE v_role_code VARCHAR(20);
  DECLARE v_msg VARCHAR(128);

  SELECT min_coverage, max_coverage INTO v_min, v_max
    FROM coverage_tier WHERE tier_id = NEW.tier_id;
  SET v_role_code = (SELECT r.role_code
                     FROM app_user u
                     INNER JOIN role r ON u.role_id = r.role_id
                     WHERE u.user_id = NEW.user_id);

  IF v_role_code IS NULL OR v_role_code <> 'CUSTOMER' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Only customer accounts can own policies.';
  END IF;
  IF NEW.coverage_amount < v_min OR NEW.coverage_amount > v_max THEN
    SET v_msg = CONCAT('The sum insured must be between ', FORMAT(v_min, 0), ' and ', FORMAT(v_max, 0), ' THB for this plan.');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;
  -- underwriting: no policy without an APPROVED application for its quotation
  IF NOT EXISTS (SELECT 1 FROM underwriting_application
                 WHERE quote_id = NEW.quote_id AND app_status = 'Approved') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A policy can only be issued after the application has been approved by our underwriting team.';
  END IF;

  SET NEW.remaining_coverage = NEW.coverage_amount;
  IF NEW.policy_status <> 'Cancelled' THEN
    SET NEW.policy_status = fn_policy_live_status(NEW.policy_status, NEW.start_date, NEW.end_date,
                                                  NEW.remaining_coverage, CURDATE());
  END IF;
END $$
DELIMITER ;

-- B3) policy : automatic status transitions (Active -> Exhausted when the
--     claim trigger drains remaining_coverage), no "un-cancelling"
DROP TRIGGER IF EXISTS trg_policy_before_update;
DELIMITER $$
CREATE TRIGGER trg_policy_before_update
  BEFORE UPDATE ON policy
  FOR EACH ROW
BEGIN
  IF OLD.policy_status = 'Cancelled' AND NEW.policy_status <> 'Cancelled' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A cancelled policy cannot be reinstated. Please apply for a new policy.';
  END IF;

  IF NEW.policy_status = 'Cancelled' THEN
    IF OLD.policy_status <> 'Cancelled' AND NEW.cancelled_at IS NULL THEN
      SET NEW.cancelled_at = NOW();
    END IF;
  ELSE
    SET NEW.policy_status = fn_policy_live_status(NEW.policy_status, NEW.start_date, NEW.end_date,
                                                  NEW.remaining_coverage, CURDATE());
  END IF;
END $$
DELIMITER ;

-- B4) payment : money records are never deleted, refunds are one-way
DROP TRIGGER IF EXISTS trg_payment_before_update;
DELIMITER $$
CREATE TRIGGER trg_payment_before_update
  BEFORE UPDATE ON payment
  FOR EACH ROW
BEGIN
  IF OLD.payment_status = 'Refunded' AND NEW.payment_status = 'Paid' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A refunded payment cannot be switched back to Paid.';
  END IF;
  IF NEW.amount <> OLD.amount THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Payment amounts cannot be changed. Please refund and issue a new payment.';
  END IF;
  IF NEW.payment_status = 'Refunded' AND NEW.refunded_at IS NULL THEN
    SET NEW.refunded_at = NOW();
  END IF;
END $$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_payment_before_delete;
DELIMITER $$
CREATE TRIGGER trg_payment_before_delete
  BEFORE DELETE ON payment
  FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Payment records cannot be deleted. Please issue a refund instead.';
END $$
DELIMITER ;

-- B5) policy_beneficiary : max 4 people, running total never above 100%
DROP TRIGGER IF EXISTS trg_beneficiary_before_insert;
DELIMITER $$
CREATE TRIGGER trg_beneficiary_before_insert
  BEFORE INSERT ON policy_beneficiary
  FOR EACH ROW
BEGIN
  DECLARE v_count INT;
  DECLARE v_total DECIMAL(6,2);
  DECLARE v_msg VARCHAR(128);

  SELECT COUNT(*), IFNULL(SUM(allocation_pct), 0)
    INTO v_count, v_total
    FROM policy_beneficiary
    WHERE policy_id = NEW.policy_id;

  IF v_count >= 4 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A policy can have a maximum of 4 beneficiaries.';
  END IF;
  IF v_total + NEW.allocation_pct > 100 THEN
    SET v_msg = CONCAT('Total allocation would reach ', v_total + NEW.allocation_pct, '%. Benefit allocation cannot exceed 100%.');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;
END $$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_beneficiary_before_update;
DELIMITER $$
CREATE TRIGGER trg_beneficiary_before_update
  BEFORE UPDATE ON policy_beneficiary
  FOR EACH ROW
BEGIN
  DECLARE v_total DECIMAL(6,2);
  DECLARE v_msg VARCHAR(128);

  IF NEW.policy_id <> OLD.policy_id THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A beneficiary cannot be moved to another policy.';
  END IF;

  SELECT IFNULL(SUM(allocation_pct), 0) INTO v_total
    FROM policy_beneficiary
    WHERE policy_id = NEW.policy_id
      AND beneficiary_id <> OLD.beneficiary_id;

  IF v_total + NEW.allocation_pct > 100 THEN
    SET v_msg = CONCAT('Total allocation would reach ', v_total + NEW.allocation_pct, '%. Benefit allocation cannot exceed 100%.');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;
END $$
DELIMITER ;

-- B6) claim BEFORE INSERT : the claim must make sense for its policy
DROP TRIGGER IF EXISTS trg_claim_before_insert;
DELIMITER $$
CREATE TRIGGER trg_claim_before_insert
  BEFORE INSERT ON claim
  FOR EACH ROW
BEGIN
  DECLARE v_start DATE;
  DECLARE v_end DATE;
  DECLARE v_coverage DECIMAL(12,2);
  DECLARE v_remaining DECIMAL(12,2);
  DECLARE v_status VARCHAR(20);
  DECLARE v_msg VARCHAR(128);

  IF NEW.submitted_at IS NULL THEN
    SET NEW.submitted_at = NOW();
  END IF;

  SELECT start_date, end_date, coverage_amount, remaining_coverage, policy_status
    INTO v_start, v_end, v_coverage, v_remaining, v_status
    FROM policy
    WHERE policy_id = NEW.policy_id;

  IF v_status = 'Cancelled' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Cancelled policies cannot receive claims.';
  ELSEIF NEW.incident_date < v_start OR NEW.incident_date > v_end THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'The date of service must fall within the policy coverage period.';
  ELSEIF NEW.incident_date > DATE(NEW.submitted_at) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'The date of service cannot be in the future.';
  ELSEIF DATE(NEW.submitted_at) > DATE_ADD(v_end, INTERVAL 30 DAY) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Claims must be submitted within 30 days after the policy end date.';
  ELSEIF v_remaining <= 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'The benefit limit of this policy has been fully used.';
  ELSEIF NEW.claimed_amount > v_coverage THEN
    SET v_msg = CONCAT('The claimed amount cannot exceed the sum insured of ', FORMAT(v_coverage, 2), ' THB.');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  SET NEW.claim_status = 'Pending';
  SET NEW.approved_amount = NULL;
  SET NEW.reviewed_by = NULL;
  SET NEW.reviewed_at = NULL;
  SET NEW.review_note = NULL;
END $$
DELIMITER ;

-- B7) claim AFTER INSERT : audit "claim submitted" (Lab 9 audit table)
DROP TRIGGER IF EXISTS trg_claim_after_insert;
DELIMITER $$
CREATE TRIGGER trg_claim_after_insert
  AFTER INSERT ON claim
  FOR EACH ROW
BEGIN
  DECLARE v_remaining DECIMAL(12,2);
  DECLARE v_owner INT;
  SELECT remaining_coverage, user_id INTO v_remaining, v_owner
    FROM policy WHERE policy_id = NEW.policy_id;
  INSERT INTO claim_status_audit
    SET claim_id = NEW.claim_id,
        policy_id = NEW.policy_id,
        old_status = NULL,
        new_status = NEW.claim_status,
        amount = NEW.claimed_amount,
        remaining_before = v_remaining,
        remaining_after = v_remaining,
        changed_by = v_owner,
        actiontype = 'claim submitted',
        changedate = NEW.submitted_at;
END $$
DELIMITER ;

-- B8) claim BEFORE UPDATE : review rules (decisions are final, approved
--     amount <= claimed - deductible and <= remaining coverage)
DROP TRIGGER IF EXISTS trg_claim_before_update;
DELIMITER $$
CREATE TRIGGER trg_claim_before_update
  BEFORE UPDATE ON claim
  FOR EACH ROW
BEGIN
  DECLARE v_remaining DECIMAL(12,2);
  DECLARE v_deductible DECIMAL(10,2);
  DECLARE v_policy_status VARCHAR(20);
  DECLARE v_msg VARCHAR(128);

  IF NEW.policy_id <> OLD.policy_id THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A claim cannot be moved to another policy.';
  END IF;

  IF OLD.claim_status <> 'Pending' THEN
    IF NEW.claim_status <> OLD.claim_status
       OR NOT (NEW.approved_amount <=> OLD.approved_amount)
       OR NEW.claimed_amount <> OLD.claimed_amount THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'This claim has already been assessed and its decision is final.';
    END IF;

  ELSEIF NEW.claim_status = 'Approved' THEN
    SELECT po.remaining_coverage, t.deductible, po.policy_status
      INTO v_remaining, v_deductible, v_policy_status
      FROM policy po
      INNER JOIN coverage_tier t ON po.tier_id = t.tier_id
      WHERE po.policy_id = NEW.policy_id;

    IF v_policy_status = 'Cancelled' THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Claims on a cancelled policy cannot be approved.';
    ELSEIF NEW.reviewed_by IS NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'A claims officer must be recorded to approve a claim.';
    ELSEIF NEW.approved_amount IS NULL OR NEW.approved_amount <= 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'An approved claim needs an approved amount greater than zero.';
    ELSEIF NEW.approved_amount > NEW.claimed_amount - v_deductible THEN
      SET v_msg = CONCAT('Approved amount cannot exceed claimed amount minus the deductible (',
                         FORMAT(GREATEST(NEW.claimed_amount - v_deductible, 0), 2), ' THB).');
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
    ELSEIF NEW.approved_amount > v_remaining THEN
      SET v_msg = CONCAT('Approved amount exceeds the remaining benefit of ', FORMAT(v_remaining, 2), ' THB.');
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
    END IF;
    IF NEW.reviewed_at IS NULL THEN
      SET NEW.reviewed_at = NOW();
    END IF;

  ELSEIF NEW.claim_status = 'Rejected' THEN
    IF NEW.reviewed_by IS NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'A claims officer must be recorded to decline a claim.';
    ELSEIF NEW.review_note IS NULL OR TRIM(NEW.review_note) = '' THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Please provide the reason for declining this claim.';
    END IF;
    SET NEW.approved_amount = NULL;
    IF NEW.reviewed_at IS NULL THEN
      SET NEW.reviewed_at = NOW();
    END IF;

  ELSE
    SET NEW.approved_amount = NULL;
  END IF;
END $$
DELIMITER ;

-- B9) claim AFTER UPDATE : *** deduct the approved amount from the policy ***
DROP TRIGGER IF EXISTS trg_claim_after_update;
DELIMITER $$
CREATE TRIGGER trg_claim_after_update
  AFTER UPDATE ON claim
  FOR EACH ROW
BEGIN
  IF OLD.claim_status = 'Pending' AND NEW.claim_status = 'Approved' THEN
    UPDATE policy
      SET remaining_coverage = remaining_coverage - NEW.approved_amount
      WHERE policy_id = NEW.policy_id;
  END IF;
END $$
DELIMITER ;

-- B10) claim AFTER UPDATE (runs second, FOLLOWS) : audit every decision
DROP TRIGGER IF EXISTS trg_claim_after_update_audit;
DELIMITER $$
CREATE TRIGGER trg_claim_after_update_audit
  AFTER UPDATE ON claim
  FOR EACH ROW
  FOLLOWS trg_claim_after_update
BEGIN
  DECLARE v_after DECIMAL(12,2);
  IF NOT (OLD.claim_status <=> NEW.claim_status) THEN
    SET v_after = (SELECT remaining_coverage FROM policy WHERE policy_id = NEW.policy_id);
    INSERT INTO claim_status_audit
      SET claim_id = NEW.claim_id,
          policy_id = NEW.policy_id,
          old_status = OLD.claim_status,
          new_status = NEW.claim_status,
          amount = NEW.approved_amount,
          remaining_before = IF(NEW.claim_status = 'Approved', v_after + NEW.approved_amount, v_after),
          remaining_after = v_after,
          changed_by = NEW.reviewed_by,
          actiontype = CONCAT('claim ', LOWER(NEW.claim_status)),
          changedate = IFNULL(NEW.reviewed_at, NOW());
  END IF;
END $$
DELIMITER ;

-- B11) claim BEFORE DELETE : only Pending claims may be withdrawn
DROP TRIGGER IF EXISTS trg_claim_before_delete;
DELIMITER $$
CREATE TRIGGER trg_claim_before_delete
  BEFORE DELETE ON claim
  FOR EACH ROW
BEGIN
  IF OLD.claim_status <> 'Pending' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Assessed claims cannot be withdrawn.';
  END IF;
END $$
DELIMITER ;


-- B12) underwriting_application BEFORE INSERT : one valid quotation, owned
--      by the applicant, still within its 7-day validity. Every new
--      application starts as 'Pending' whatever the caller sends.
DROP TRIGGER IF EXISTS trg_application_before_insert;
DELIMITER $$
CREATE TRIGGER trg_application_before_insert
  BEFORE INSERT ON underwriting_application
  FOR EACH ROW
BEGIN
  DECLARE v_quote_user INT;
  DECLARE v_quote_status VARCHAR(20);
  DECLARE v_expires DATETIME;

  SELECT user_id, quote_status, expires_at INTO v_quote_user, v_quote_status, v_expires
    FROM premium_quote WHERE quote_id = NEW.quote_id;

  IF v_quote_user IS NULL OR v_quote_user <> NEW.user_id THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'This quotation does not belong to your account.';
  END IF;
  IF v_quote_status <> 'Open' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Applications can only be submitted for a valid quotation.';
  END IF;
  IF v_expires < NEW.submitted_at THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'This quotation has expired. Please request a new quotation.';
  END IF;
  IF TRIM(IFNULL(NEW.occupation, '')) = '' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Please enter your occupation.';
  END IF;

  SET NEW.occupation = TRIM(NEW.occupation),
      NEW.app_status = 'Pending',
      NEW.reviewed_by = NULL,
      NEW.review_note = NULL,
      NEW.reviewed_at = NULL;
END $$
DELIMITER ;

-- B13) underwriting_application BEFORE UPDATE : decisions are final,
--      only officers decide, a decline needs a reason
DROP TRIGGER IF EXISTS trg_application_before_update;
DELIMITER $$
CREATE TRIGGER trg_application_before_update
  BEFORE UPDATE ON underwriting_application
  FOR EACH ROW
BEGIN
  DECLARE v_role VARCHAR(20);

  IF OLD.app_status <> 'Pending' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'This application has already been assessed and the decision is final.';
  END IF;

  IF NEW.app_status <> 'Pending' THEN
    SET v_role = (SELECT r.role_code FROM app_user u
                  INNER JOIN role r ON u.role_id = r.role_id
                  WHERE u.user_id = NEW.reviewed_by);
    IF v_role IS NULL OR v_role NOT IN ('STAFF', 'ADMIN') THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only officers can assess applications.';
    END IF;
    IF NEW.app_status = 'Rejected' AND TRIM(IFNULL(NEW.review_note, '')) = '' THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Please provide the reason for declining this application.';
    END IF;
    IF NEW.reviewed_at IS NULL THEN
      SET NEW.reviewed_at = NOW();
    END IF;
  END IF;
END $$
DELIMITER ;

-- B14) underwriting_application AFTER UPDATE : the decision drives the quote.
--      Approved -> the customer gets 7 days from approval to pay
--      Rejected -> the quotation is closed ('Declined') and can never be paid
DROP TRIGGER IF EXISTS trg_application_after_update;
DELIMITER $$
CREATE TRIGGER trg_application_after_update
  AFTER UPDATE ON underwriting_application
  FOR EACH ROW
BEGIN
  IF OLD.app_status = 'Pending' AND NEW.app_status = 'Approved' THEN
    UPDATE premium_quote
      SET expires_at = DATE_ADD(NEW.reviewed_at, INTERVAL 7 DAY)
      WHERE quote_id = NEW.quote_id;
  ELSEIF OLD.app_status = 'Pending' AND NEW.app_status = 'Rejected' THEN
    UPDATE premium_quote
      SET quote_status = 'Declined'
      WHERE quote_id = NEW.quote_id;
  END IF;
END $$
DELIMITER ;

-- B15) application_document BEFORE INSERT : documents only while the
--      application is still under review, at most 5 per application
DROP TRIGGER IF EXISTS trg_document_before_insert;
DELIMITER $$
CREATE TRIGGER trg_document_before_insert
  BEFORE INSERT ON application_document
  FOR EACH ROW
BEGIN
  IF (SELECT app_status FROM underwriting_application
      WHERE application_id = NEW.application_id) <> 'Pending' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Documents cannot be added after the application has been assessed.';
  END IF;
  IF (SELECT COUNT(*) FROM application_document WHERE application_id = NEW.application_id) >= 5 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'An application can have a maximum of 5 documents.';
  END IF;
END $$
DELIMITER ;


-- =====================================================================
-- PART C : VIEWS (Lab 8, Lab 14 - stored queries used by Django)
-- =====================================================================

-- C1) Product catalog with "starting from" price and popularity
DROP VIEW IF EXISTS vw_catalog;
CREATE VIEW vw_catalog AS
  SELECT p.product_id, p.product_code, p.product_name, p.tagline, p.description,
         p.category, p.thumbnail_path, p.requires_beneficiary, p.is_active,
         COUNT(t.tier_id) AS tier_count,
         MIN(ROUND(t.base_annual_premium * t.duration_months / 12, 2)) AS starting_premium,
         MIN(t.min_coverage) AS min_coverage,
         MAX(t.max_coverage) AS max_coverage,
         MIN(t.duration_months) AS duration_months,
         (SELECT COUNT(*)
            FROM policy po
            INNER JOIN coverage_tier t2 ON po.tier_id = t2.tier_id
            WHERE t2.product_id = p.product_id
              AND po.policy_status <> 'Cancelled') AS policies_sold
  FROM product AS p
  LEFT OUTER JOIN coverage_tier AS t
    ON p.product_id = t.product_id
  GROUP BY p.product_id, p.product_code, p.product_name, p.tagline, p.description,
           p.category, p.thumbnail_path, p.requires_beneficiary, p.is_active;

-- C2) Quote with the full premium breakdown
DROP VIEW IF EXISTS vw_quote_details;
CREATE VIEW vw_quote_details AS
  SELECT q.quote_id, q.user_id, q.tier_id, t.tier_name, t.tier_level,
         t.min_coverage, t.max_coverage, t.base_annual_premium, t.deductible,
         t.duration_months, t.perks,
         p.product_id, p.product_code, p.product_name, p.thumbnail_path, p.requires_beneficiary,
         q.coverage_amount, q.insured_age, q.risk_level,
         fn_factor_label(p.product_id, 'AGE', q.insured_age) AS age_label,
         fn_factor_label(p.product_id, 'RISK', q.risk_level) AS risk_label,
         q.age_multiplier, q.risk_multiplier,
         ROUND(q.coverage_amount / t.min_coverage, 4) AS coverage_ratio,
         ROUND(t.duration_months / 12, 4) AS duration_factor,
         q.quoted_premium,
         -- Open -> In review -> Approved -> Converted   (or Declined / Expired)
         CASE WHEN q.quote_status IN ('Converted', 'Declined') THEN q.quote_status
              WHEN a.app_status = 'Pending' THEN 'In review'
              WHEN q.quote_status = 'Expired' OR q.expires_at < NOW() THEN 'Expired'
              WHEN a.app_status = 'Approved' THEN 'Approved'
              ELSE 'Open' END AS live_status,
         q.created_at, q.expires_at,
         a.application_id, a.application_number, a.app_status,
         a.review_note AS application_note,
         a.submitted_at AS application_submitted_at,
         a.reviewed_at AS application_reviewed_at
  FROM premium_quote AS q
  INNER JOIN coverage_tier AS t ON q.tier_id = t.tier_id
  INNER JOIN product AS p ON t.product_id = p.product_id
  LEFT OUTER JOIN underwriting_application AS a ON a.quote_id = q.quote_id;

-- C3) My Policies & Coverage Tracker (Module 4)
DROP VIEW IF EXISTS vw_policy_overview;
CREATE VIEW vw_policy_overview AS
  SELECT po.policy_id, po.policy_number, po.user_id,
         CONCAT(u.first_name, ' ', u.last_name) AS customer_name, u.email AS customer_email,
         p.product_id, p.product_code, p.product_name, p.category, p.thumbnail_path, p.requires_beneficiary,
         t.tier_id, t.tier_name, t.deductible, t.duration_months,
         po.coverage_amount, po.remaining_coverage,
         po.coverage_amount - po.remaining_coverage AS coverage_used,
         ROUND((po.coverage_amount - po.remaining_coverage) / po.coverage_amount * 100, 1) AS coverage_used_pct,
         po.premium_amount, po.start_date, po.end_date,
         po.policy_status AS stored_status,
         fn_policy_live_status(po.policy_status, po.start_date, po.end_date, po.remaining_coverage, CURDATE()) AS live_status,
         GREATEST(DATEDIFF(po.end_date, CURDATE()), 0) AS days_remaining,
         DATEDIFF(po.end_date, po.start_date) + 1 AS total_days,
         ROUND(LEAST(GREATEST(DATEDIFF(CURDATE(), po.start_date), 0), DATEDIFF(po.end_date, po.start_date) + 1)
               / (DATEDIFF(po.end_date, po.start_date) + 1) * 100, 1) AS time_elapsed_pct,
         DATE_ADD(po.end_date, INTERVAL 30 DAY) AS claim_deadline,
         (SELECT COUNT(*) FROM claim c WHERE c.policy_id = po.policy_id) AS claim_count,
         (SELECT COUNT(*) FROM claim c WHERE c.policy_id = po.policy_id AND c.claim_status = 'Pending') AS pending_claims,
         (SELECT COUNT(*) FROM policy_beneficiary b WHERE b.policy_id = po.policy_id) AS beneficiary_count,
         fn_beneficiary_total(po.policy_id) AS beneficiary_total,
         po.created_at, po.cancelled_at
  FROM policy AS po
  INNER JOIN app_user AS u ON po.user_id = u.user_id
  INNER JOIN coverage_tier AS t ON po.tier_id = t.tier_id
  INNER JOIN product AS p ON t.product_id = p.product_id;

-- C4) Beneficiary allocation check (flags policies that are not at 100%)
DROP VIEW IF EXISTS vw_beneficiary_check;
CREATE VIEW vw_beneficiary_check AS
  SELECT po.policy_id, po.policy_number, po.user_id, p.product_name, p.requires_beneficiary,
         fn_policy_live_status(po.policy_status, po.start_date, po.end_date, po.remaining_coverage, CURDATE()) AS live_status,
         COUNT(b.beneficiary_id) AS beneficiary_count,
         IFNULL(SUM(b.allocation_pct), 0) AS total_pct,
         CASE WHEN IFNULL(SUM(b.allocation_pct), 0) = 100 THEN 'Complete'
              WHEN p.requires_beneficiary = 1 THEN 'Action needed'
              WHEN COUNT(b.beneficiary_id) = 0 THEN 'Optional'
              ELSE 'Incomplete' END AS allocation_status
  FROM policy AS po
  INNER JOIN coverage_tier AS t ON po.tier_id = t.tier_id
  INNER JOIN product AS p ON t.product_id = p.product_id
  LEFT OUTER JOIN policy_beneficiary AS b ON b.policy_id = po.policy_id
  GROUP BY po.policy_id, po.policy_number, po.user_id, p.product_name, p.requires_beneficiary,
           po.policy_status, po.start_date, po.end_date, po.remaining_coverage;

-- C5) Claims with everything staff need to decide (Module 5)
DROP VIEW IF EXISTS vw_claim_details;
CREATE VIEW vw_claim_details AS
  SELECT c.claim_id, c.claim_number, c.policy_id, po.policy_number, po.user_id,
         CONCAT(u.first_name, ' ', u.last_name) AS customer_name,
         u.email AS customer_email, u.avatar_path AS customer_avatar,
         p.product_id, p.product_name, p.thumbnail_path, t.tier_name, t.deductible,
         po.coverage_amount, po.remaining_coverage,
         fn_policy_live_status(po.policy_status, po.start_date, po.end_date, po.remaining_coverage, CURDATE()) AS policy_status,
         po.start_date, po.end_date,
         c.incident_date, c.incident_title, c.incident_description,
         c.claimed_amount, c.approved_amount, c.claim_status, c.review_note,
         c.submitted_at, c.reviewed_at, c.reviewed_by,
         CONCAT(s.first_name, ' ', s.last_name) AS reviewer_name,
         GREATEST(LEAST(c.claimed_amount - t.deductible, po.remaining_coverage), 0) AS max_approvable,
         (SELECT COUNT(*) FROM claim_evidence e WHERE e.claim_id = c.claim_id) AS evidence_count,
         (SELECT e.image_path FROM claim_evidence e WHERE e.claim_id = c.claim_id
           ORDER BY e.evidence_id LIMIT 1) AS first_evidence_path,
         TIMESTAMPDIFF(HOUR, c.submitted_at, IFNULL(c.reviewed_at, NOW())) AS hours_open
  FROM claim AS c
  INNER JOIN policy AS po ON c.policy_id = po.policy_id
  INNER JOIN app_user AS u ON po.user_id = u.user_id
  INNER JOIN coverage_tier AS t ON po.tier_id = t.tier_id
  INNER JOIN product AS p ON t.product_id = p.product_id
  LEFT OUTER JOIN app_user AS s ON c.reviewed_by = s.user_id;

-- C6) Best-selling plans (Module 6)
DROP VIEW IF EXISTS vw_product_sales;
CREATE VIEW vw_product_sales AS
  SELECT p.product_id, p.product_name, p.category, t.tier_id, t.tier_name, t.tier_level,
         COUNT(po.policy_id) AS policies_sold,
         COUNT(DISTINCT po.user_id) AS unique_customers,
         IFNULL(SUM(po.premium_amount), 0) AS premium_written,
         IFNULL(SUM(po.coverage_amount), 0) AS coverage_written
  FROM product AS p
  INNER JOIN coverage_tier AS t ON p.product_id = t.product_id
  LEFT OUTER JOIN policy AS po ON po.tier_id = t.tier_id AND po.policy_status <> 'Cancelled'
  GROUP BY p.product_id, p.product_name, p.category, t.tier_id, t.tier_name, t.tier_level;

-- C7) Premium collected per month (Module 6)
DROP VIEW IF EXISTS vw_monthly_premium;
CREATE VIEW vw_monthly_premium AS
  SELECT DATE_FORMAT(pay.paid_at, '%Y-%m') AS period,
         COUNT(*) AS payments,
         SUM(pay.amount) AS gross_premium,
         SUM(IF(pay.payment_status = 'Refunded', pay.amount, 0)) AS refunded,
         SUM(IF(pay.payment_status = 'Paid', pay.amount, 0)) AS net_premium
  FROM payment AS pay
  GROUP BY DATE_FORMAT(pay.paid_at, '%Y-%m');

-- C8) Claim payout (loss) ratio per product (derived tables avoid join fan-out)
DROP VIEW IF EXISTS vw_claim_ratio;
CREATE VIEW vw_claim_ratio AS
  SELECT p.product_id, p.product_name, p.category,
         IFNULL(prem.net_premium, 0) AS net_premium,
         IFNULL(cl.total_claims, 0) AS total_claims,
         IFNULL(cl.approved_claims, 0) AS approved_claims,
         IFNULL(cl.rejected_claims, 0) AS rejected_claims,
         IFNULL(cl.pending_claims, 0) AS pending_claims,
         IFNULL(cl.total_payout, 0) AS total_payout,
         ROUND(IFNULL(cl.total_payout, 0) / NULLIF(prem.net_premium, 0) * 100, 1) AS loss_ratio_pct
  FROM product AS p
  LEFT OUTER JOIN
    (SELECT t.product_id, SUM(IF(pay.payment_status = 'Paid', pay.amount, 0)) AS net_premium
       FROM payment pay
       INNER JOIN policy po ON pay.policy_id = po.policy_id
       INNER JOIN coverage_tier t ON po.tier_id = t.tier_id
       GROUP BY t.product_id) AS prem
    ON prem.product_id = p.product_id
  LEFT OUTER JOIN
    (SELECT t.product_id,
            COUNT(*) AS total_claims,
            SUM(c.claim_status = 'Approved') AS approved_claims,
            SUM(c.claim_status = 'Rejected') AS rejected_claims,
            SUM(c.claim_status = 'Pending') AS pending_claims,
            SUM(IFNULL(c.approved_amount, 0)) AS total_payout
       FROM claim c
       INNER JOIN policy po ON c.policy_id = po.policy_id
       INNER JOIN coverage_tier t ON po.tier_id = t.tier_id
       GROUP BY t.product_id) AS cl
    ON cl.product_id = p.product_id;



-- C9) Underwriting applications with everything an officer needs (Module 3)
DROP VIEW IF EXISTS vw_application_details;
CREATE VIEW vw_application_details AS
  SELECT a.application_id, a.application_number, a.quote_id, a.user_id,
         CONCAT(u.first_name, ' ', u.last_name) AS customer_name,
         u.email AS customer_email, u.phone AS customer_phone, u.avatar_path AS customer_avatar,
         u.date_of_birth, fn_age(u.date_of_birth, CURDATE()) AS customer_age,
         p.product_id, p.product_code, p.product_name, p.category, p.thumbnail_path, t.tier_name,
         q.coverage_amount, q.quoted_premium, q.risk_level,
         fn_factor_label(p.product_id, 'RISK', q.risk_level) AS risk_label,
         fn_factor_label(p.product_id, 'AGE', q.insured_age) AS age_label,
         q.expires_at AS quote_expires_at, q.quote_status,
         a.occupation, a.employer, a.monthly_income, a.is_smoker, a.has_medical_history, a.health_details,
         a.app_status, a.review_note, a.submitted_at, a.reviewed_at, a.reviewed_by,
         CONCAT(s.first_name, ' ', s.last_name) AS reviewer_name,
         (SELECT COUNT(*) FROM application_document d WHERE d.application_id = a.application_id) AS document_count,
         (SELECT COUNT(*) FROM policy po WHERE po.user_id = a.user_id
            AND po.policy_status <> 'Cancelled') AS existing_policies,
         TIMESTAMPDIFF(HOUR, a.submitted_at, IFNULL(a.reviewed_at, NOW())) AS hours_open
  FROM underwriting_application AS a
  INNER JOIN app_user AS u ON a.user_id = u.user_id
  INNER JOIN premium_quote AS q ON a.quote_id = q.quote_id
  INNER JOIN coverage_tier AS t ON q.tier_id = t.tier_id
  INNER JOIN product AS p ON t.product_id = p.product_id
  LEFT OUTER JOIN app_user AS s ON a.reviewed_by = s.user_id;

-- =====================================================================
-- PART D : STORED PROCEDURES (Lab 9.1, Lab 4 transactions, Lab 14 callproc)
--   Every procedure returns ONE result set whose first column is `status`
--   ('SUCCESS' / 'ERROR' / 'DECLINED'), so Django can read it with
--   myCursor.callproc(...) + fetchall() exactly like Lab 14.
-- =====================================================================

-- D1) Register a user (customer by default). Duplicate e-mail -> handler 1062
DROP PROCEDURE IF EXISTS sp_register_user;
DELIMITER $$
CREATE PROCEDURE sp_register_user(
  IN p_role_code VARCHAR(20),
  IN p_first_name VARCHAR(60),
  IN p_last_name VARCHAR(60),
  IN p_email VARCHAR(120),
  IN p_password_hash VARCHAR(255),
  IN p_phone VARCHAR(20),
  IN p_dob DATE
)
proc_register: BEGIN
  DECLARE v_role_id INT;
  DECLARE EXIT HANDLER FOR 1062
  BEGIN
    SELECT 'ERROR' AS status,
           CONCAT('The e-mail address ', p_email, ' is already registered. Please sign in instead.') AS message,
           NULL AS user_id;
  END;

  SET v_role_id = (SELECT role_id FROM role WHERE role_code = IFNULL(p_role_code, 'CUSTOMER'));
  IF v_role_id IS NULL THEN
    SELECT 'ERROR' AS status, 'Unknown role.' AS message, NULL AS user_id;
    LEAVE proc_register;
  END IF;

  INSERT INTO app_user (role_id, email, password_hash, first_name, last_name, phone, date_of_birth)
  VALUES (v_role_id, p_email, p_password_hash, p_first_name, p_last_name, NULLIF(p_phone, ''), p_dob);

  SELECT 'SUCCESS' AS status,
         'Your BIB Assurance account has been created. Please sign in.' AS message,
         LAST_INSERT_ID() AS user_id;
END $$
DELIMITER ;

-- D2) Create a server-side quote using fn_calc_premium (Module 2)
DROP PROCEDURE IF EXISTS sp_create_quote;
DELIMITER $$
CREATE PROCEDURE sp_create_quote(
  IN p_user_id INT,
  IN p_tier_id INT,
  IN p_coverage DECIMAL(12,2),
  IN p_risk_level INT
)
proc_quote: BEGIN
  DECLARE v_dob DATE;
  DECLARE v_role VARCHAR(20);
  DECLARE v_age INT;
  DECLARE v_product_id INT;
  DECLARE v_active TINYINT;
  DECLARE v_min DECIMAL(12,2);
  DECLARE v_max DECIMAL(12,2);
  DECLARE v_age_mult DECIMAL(5,3);
  DECLARE v_risk_mult DECIMAL(5,3);
  DECLARE v_premium DECIMAL(10,2);
  DECLARE v_found INT DEFAULT 1;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_found = 0;

  SELECT u.date_of_birth, r.role_code INTO v_dob, v_role
    FROM app_user u
    INNER JOIN role r ON u.role_id = r.role_id
    WHERE u.user_id = p_user_id;
  IF v_found = 0 OR v_role <> 'CUSTOMER' OR v_dob IS NULL THEN
    SELECT 'ERROR' AS status, 'Please sign in with a customer account to request a quotation.' AS message, NULL AS quote_id;
    LEAVE proc_quote;
  END IF;

  SELECT t.product_id, p.is_active, t.min_coverage, t.max_coverage
    INTO v_product_id, v_active, v_min, v_max
    FROM coverage_tier t
    INNER JOIN product p ON t.product_id = p.product_id
    WHERE t.tier_id = p_tier_id;
  IF v_found = 0 OR v_active = 0 THEN
    SELECT 'ERROR' AS status, 'This plan is currently not available.' AS message, NULL AS quote_id;
    LEAVE proc_quote;
  END IF;

  IF p_coverage IS NULL OR p_coverage < v_min OR p_coverage > v_max THEN
    SELECT 'ERROR' AS status,
           CONCAT('The sum insured must be between ', FORMAT(v_min, 0), ' and ', FORMAT(v_max, 0), ' THB for this plan.') AS message,
           NULL AS quote_id;
    LEAVE proc_quote;
  END IF;

  IF p_risk_level IS NULL OR p_risk_level NOT BETWEEN 1 AND 4 THEN
    SELECT 'ERROR' AS status, 'Please select an underwriting class.' AS message, NULL AS quote_id;
    LEAVE proc_quote;
  END IF;

  SET v_age = fn_age(v_dob, CURDATE());
  SET v_age_mult = fn_get_multiplier(v_product_id, 'AGE', v_age);
  SET v_risk_mult = fn_get_multiplier(v_product_id, 'RISK', p_risk_level);
  SET v_premium = fn_calc_premium(p_tier_id, v_age, p_risk_level, p_coverage);

  INSERT INTO premium_quote (user_id, tier_id, coverage_amount, insured_age, risk_level,
                             age_multiplier, risk_multiplier, quoted_premium, quote_status,
                             created_at, expires_at)
  VALUES (p_user_id, p_tier_id, p_coverage, v_age, p_risk_level,
          v_age_mult, v_risk_mult, v_premium, 'Open',
          NOW(), DATE_ADD(NOW(), INTERVAL 7 DAY));

  SELECT 'SUCCESS' AS status, 'Your quotation is ready. Next, please submit your application for review.' AS message, LAST_INSERT_ID() AS quote_id;
END $$
DELIMITER ;

-- D3) *** ACID CHECKOUT *** (Module 3, Lab 4)
--     Policy + policy number + payment + quote conversion + log happen in
--     ONE transaction.  Test card 4000 0000 0000 0002 is always declined:
--     the policy that was already inserted is ROLLED BACK.
DROP PROCEDURE IF EXISTS sp_checkout_policy;
DELIMITER $$
CREATE PROCEDURE sp_checkout_policy(
  IN p_quote_id INT,
  IN p_user_id INT,
  IN p_method VARCHAR(20),
  IN p_card_number VARCHAR(25),
  IN p_start_date DATE
)
proc_checkout: BEGIN
  DECLARE v_quote_user INT;
  DECLARE v_tier_id INT;
  DECLARE v_coverage DECIMAL(12,2);
  DECLARE v_premium DECIMAL(10,2);
  DECLARE v_quote_status VARCHAR(20);
  DECLARE v_expires DATETIME;
  DECLARE v_months INT;
  DECLARE v_policy_id INT;
  DECLARE v_policy_number VARCHAR(20);
  DECLARE v_end_date DATE;
  DECLARE v_card VARCHAR(25);
  DECLARE v_card_last4 CHAR(4) DEFAULT NULL;
  DECLARE v_txn VARCHAR(40);
  DECLARE v_found INT DEFAULT 1;

  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_found = 0;

  -- duplicate key (e.g. same quote converted twice by a double click)
  DECLARE EXIT HANDLER FOR 1062
  BEGIN
    ROLLBACK;
    INSERT INTO checkout_log (user_id, quote_id, amount, payment_method, card_last4, result, message)
    VALUES (p_user_id, p_quote_id, v_premium, p_method, v_card_last4, 'ERROR',
            'Duplicate payment prevented: this quotation has already been issued as a policy.');
    SELECT 'ERROR' AS status,
           'This quotation has already been issued as a policy. You have not been charged twice.' AS message,
           NULL AS policy_id, NULL AS policy_number;
  END;

  -- any other error inside the transaction
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    INSERT INTO checkout_log (user_id, quote_id, amount, payment_method, card_last4, result, message)
    VALUES (p_user_id, p_quote_id, v_premium, p_method, v_card_last4, 'ERROR',
            'Purchase not completed because of a system error. No payment was taken.');
    SELECT 'ERROR' AS status,
           'We could not complete your purchase because of a system error. No payment was taken.' AS message,
           NULL AS policy_id, NULL AS policy_number;
  END;

  -- 1) validate the quote ------------------------------------------------
  SELECT q.user_id, q.tier_id, q.coverage_amount, q.quoted_premium, q.quote_status, q.expires_at, t.duration_months
    INTO v_quote_user, v_tier_id, v_coverage, v_premium, v_quote_status, v_expires, v_months
    FROM premium_quote q
    INNER JOIN coverage_tier t ON q.tier_id = t.tier_id
    WHERE q.quote_id = p_quote_id;

  IF v_found = 0 OR v_quote_user <> p_user_id THEN
    SELECT 'ERROR' AS status, 'Quotation not found for this account.' AS message, NULL AS policy_id, NULL AS policy_number;
    LEAVE proc_checkout;
  END IF;

  IF v_quote_status = 'Converted' THEN
    SELECT 'ERROR' AS status, 'This quotation has already been issued as a policy.' AS message, NULL AS policy_id, NULL AS policy_number;
    LEAVE proc_checkout;
  END IF;

  -- underwriting: payment is only possible after an officer approved the application
  IF v_quote_status = 'Declined' THEN
    SELECT 'ERROR' AS status, 'This application was declined, so the quotation cannot be purchased.' AS message,
           NULL AS policy_id, NULL AS policy_number;
    LEAVE proc_checkout;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM underwriting_application
                 WHERE quote_id = p_quote_id AND app_status = 'Approved') THEN
    SELECT 'ERROR' AS status, 'Your application must be approved by our underwriting team before you can pay.' AS message,
           NULL AS policy_id, NULL AS policy_number;
    LEAVE proc_checkout;
  END IF;

  IF v_quote_status = 'Expired' OR v_expires < NOW() THEN
    UPDATE premium_quote SET quote_status = 'Expired' WHERE quote_id = p_quote_id;
    INSERT INTO checkout_log (user_id, quote_id, amount, payment_method, result, message)
    VALUES (p_user_id, p_quote_id, v_premium, p_method, 'ERROR', 'Quotation expired before payment.');
    SELECT 'ERROR' AS status, 'This quotation has expired (quotations are valid for 7 days). Please request a new quotation.' AS message,
           NULL AS policy_id, NULL AS policy_number;
    LEAVE proc_checkout;
  END IF;

  IF p_start_date IS NULL OR p_start_date < CURDATE() OR p_start_date > DATE_ADD(CURDATE(), INTERVAL 30 DAY) THEN
    SELECT 'ERROR' AS status, 'The coverage start date must be between today and 30 days from today.' AS message,
           NULL AS policy_id, NULL AS policy_number;
    LEAVE proc_checkout;
  END IF;

  IF p_method IS NULL OR p_method NOT IN ('Card', 'PromptPay', 'BankTransfer') THEN
    SELECT 'ERROR' AS status, 'Please select a payment method.' AS message, NULL AS policy_id, NULL AS policy_number;
    LEAVE proc_checkout;
  END IF;

  IF p_method = 'Card' THEN
    SET v_card = REPLACE(REPLACE(IFNULL(p_card_number, ''), ' ', ''), '-', '');
    IF v_card NOT REGEXP '^[0-9]{16}$' THEN
      SELECT 'ERROR' AS status, 'Please enter a valid 16-digit card number.' AS message,
             NULL AS policy_id, NULL AS policy_number;
      LEAVE proc_checkout;
    END IF;
    SET v_card_last4 = RIGHT(v_card, 4);
  END IF;

  SET v_end_date = DATE_SUB(DATE_ADD(p_start_date, INTERVAL v_months MONTH), INTERVAL 1 DAY);

  -- 2) the ACID part -------------------------------------------------------
  START TRANSACTION;

    INSERT INTO policy (policy_number, user_id, tier_id, quote_id, coverage_amount, remaining_coverage,
                        premium_amount, start_date, end_date, policy_status, created_at)
    VALUES (NULL, p_user_id, v_tier_id, p_quote_id, v_coverage, v_coverage,
            v_premium, p_start_date, v_end_date, 'Active', NOW());

    SET v_policy_id = LAST_INSERT_ID();
    SET v_policy_number = fn_format_number('BIB', v_policy_id, CURDATE());
    UPDATE policy SET policy_number = v_policy_number WHERE policy_id = v_policy_id;

    -- 3) mock payment gateway: the decline test card --------------------
    IF p_method = 'Card' AND v_card = '4000000000000002' THEN
      ROLLBACK;
      INSERT INTO checkout_log (user_id, quote_id, policy_id, amount, payment_method, card_last4, result, message)
      VALUES (p_user_id, p_quote_id, NULL, v_premium, p_method, v_card_last4, 'DECLINED',
              CONCAT('Payment declined by the card issuer. Policy ', v_policy_number, ' was not issued.'));
      SELECT 'DECLINED' AS status,
             CONCAT('Your card ending ', v_card_last4, ' was declined by the issuing bank. ',
                    'No payment was taken and no policy was issued.') AS message,
             NULL AS policy_id, v_policy_number AS policy_number;
      LEAVE proc_checkout;
    END IF;

    SET v_txn = CONCAT('TXN-', DATE_FORMAT(NOW(), '%Y%m%d%H%i%s'), '-', LPAD(v_policy_id, 6, '0'));
    INSERT INTO payment (policy_id, user_id, amount, payment_method, card_last4, payment_status, transaction_ref, paid_at)
    VALUES (v_policy_id, p_user_id, v_premium, p_method, v_card_last4, 'Paid', v_txn, NOW());

    UPDATE premium_quote SET quote_status = 'Converted' WHERE quote_id = p_quote_id;

    INSERT INTO checkout_log (user_id, quote_id, policy_id, amount, payment_method, card_last4, result, message)
    VALUES (p_user_id, p_quote_id, v_policy_id, v_premium, p_method, v_card_last4, 'SUCCESS',
            CONCAT('Policy ', v_policy_number, ' issued. Payment ', v_txn, '.'));

  COMMIT;

  SELECT 'SUCCESS' AS status,
         CONCAT('Thank you. Policy ', v_policy_number, ' has been issued.') AS message,
         v_policy_id AS policy_id, v_policy_number AS policy_number;
END $$
DELIMITER ;

-- D4) Save up to 4 beneficiaries in ONE transaction. COMMIT only when the
--     total is exactly 100% (or 0% for plans that don't require any).
DROP PROCEDURE IF EXISTS sp_save_beneficiaries;
DELIMITER $$
CREATE PROCEDURE sp_save_beneficiaries(
  IN p_policy_id INT,
  IN p_user_id INT,
  IN p_name1 VARCHAR(120), IN p_rel1 VARCHAR(40), IN p_pct1 DECIMAL(5,2),
  IN p_name2 VARCHAR(120), IN p_rel2 VARCHAR(40), IN p_pct2 DECIMAL(5,2),
  IN p_name3 VARCHAR(120), IN p_rel3 VARCHAR(40), IN p_pct3 DECIMAL(5,2),
  IN p_name4 VARCHAR(120), IN p_rel4 VARCHAR(40), IN p_pct4 DECIMAL(5,2)
)
proc_beneficiary: BEGIN
  DECLARE v_owner INT;
  DECLARE v_status VARCHAR(20);
  DECLARE v_requires TINYINT;
  DECLARE v_total DECIMAL(6,2);
  DECLARE v_found INT DEFAULT 1;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_found = 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;   -- pass the trigger's SIGNAL message up to Django
  END;

  SELECT po.user_id,
         fn_policy_live_status(po.policy_status, po.start_date, po.end_date, po.remaining_coverage, CURDATE()),
         p.requires_beneficiary
    INTO v_owner, v_status, v_requires
    FROM policy po
    INNER JOIN coverage_tier t ON po.tier_id = t.tier_id
    INNER JOIN product p ON t.product_id = p.product_id
    WHERE po.policy_id = p_policy_id;

  IF v_found = 0 OR v_owner <> p_user_id THEN
    SELECT 'ERROR' AS status, 'Policy not found for this account.' AS message, 0 AS total_pct;
    LEAVE proc_beneficiary;
  END IF;
  IF v_status NOT IN ('Active', 'Scheduled', 'Exhausted') THEN
    SELECT 'ERROR' AS status, CONCAT('Beneficiaries cannot be changed on a ', LOWER(v_status), ' policy.') AS message, 0 AS total_pct;
    LEAVE proc_beneficiary;
  END IF;

  START TRANSACTION;
    DELETE FROM policy_beneficiary WHERE policy_id = p_policy_id;

    IF TRIM(IFNULL(p_name1, '')) <> '' THEN
      INSERT INTO policy_beneficiary (policy_id, full_name, relationship, allocation_pct)
      VALUES (p_policy_id, TRIM(p_name1), TRIM(p_rel1), p_pct1);
    END IF;
    IF TRIM(IFNULL(p_name2, '')) <> '' THEN
      INSERT INTO policy_beneficiary (policy_id, full_name, relationship, allocation_pct)
      VALUES (p_policy_id, TRIM(p_name2), TRIM(p_rel2), p_pct2);
    END IF;
    IF TRIM(IFNULL(p_name3, '')) <> '' THEN
      INSERT INTO policy_beneficiary (policy_id, full_name, relationship, allocation_pct)
      VALUES (p_policy_id, TRIM(p_name3), TRIM(p_rel3), p_pct3);
    END IF;
    IF TRIM(IFNULL(p_name4, '')) <> '' THEN
      INSERT INTO policy_beneficiary (policy_id, full_name, relationship, allocation_pct)
      VALUES (p_policy_id, TRIM(p_name4), TRIM(p_rel4), p_pct4);
    END IF;

    SET v_total = fn_beneficiary_total(p_policy_id);

  IF v_total = 100.00 THEN
    COMMIT;
    SELECT 'SUCCESS' AS status, 'Beneficiary details have been updated.' AS message, v_total AS total_pct;
  ELSEIF v_total = 0 AND v_requires = 0 THEN
    COMMIT;
    SELECT 'SUCCESS' AS status, 'All beneficiaries have been removed.' AS message, v_total AS total_pct;
  ELSE
    ROLLBACK;
    SELECT 'ERROR' AS status,
           CONCAT('Benefit allocation must total exactly 100% (currently ', v_total, '%). No changes were saved.') AS message,
           v_total AS total_pct;
  END IF;
END $$
DELIMITER ;

-- D5) Submit a claim + up to 3 evidence photos atomically (Module 5)
--     p_submitted_at is NULL from the web app (= NOW()); the seed script
--     passes historical timestamps.
DROP PROCEDURE IF EXISTS sp_submit_claim;
DELIMITER $$
CREATE PROCEDURE sp_submit_claim(
  IN p_user_id INT,
  IN p_policy_id INT,
  IN p_incident_date DATE,
  IN p_title VARCHAR(120),
  IN p_description TEXT,
  IN p_claimed_amount DECIMAL(12,2),
  IN p_image1 VARCHAR(255), IN p_caption1 VARCHAR(160),
  IN p_image2 VARCHAR(255), IN p_caption2 VARCHAR(160),
  IN p_image3 VARCHAR(255), IN p_caption3 VARCHAR(160),
  IN p_submitted_at DATETIME
)
proc_claim: BEGIN
  DECLARE v_owner INT;
  DECLARE v_claim_id INT;
  DECLARE v_claim_number VARCHAR(20);
  DECLARE v_submitted DATETIME;
  DECLARE v_found INT DEFAULT 1;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_found = 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;   -- trigger messages (coverage period, 30-day window...) reach Django
  END;

  SET v_submitted = IFNULL(p_submitted_at, NOW());

  SELECT user_id INTO v_owner FROM policy WHERE policy_id = p_policy_id;
  IF v_found = 0 OR v_owner <> p_user_id THEN
    SELECT 'ERROR' AS status, 'Policy not found for this account.' AS message, NULL AS claim_id, NULL AS claim_number;
    LEAVE proc_claim;
  END IF;
  IF TRIM(IFNULL(p_image1, '')) = '' THEN
    SELECT 'ERROR' AS status, 'Please attach at least one supporting document.' AS message,
           NULL AS claim_id, NULL AS claim_number;
    LEAVE proc_claim;
  END IF;

  START TRANSACTION;
    INSERT INTO claim (policy_id, incident_date, incident_title, incident_description, claimed_amount, submitted_at)
    VALUES (p_policy_id, p_incident_date, p_title, p_description, p_claimed_amount, v_submitted);

    SET v_claim_id = LAST_INSERT_ID();
    SET v_claim_number = fn_format_number('CLM', v_claim_id, DATE(v_submitted));
    UPDATE claim SET claim_number = v_claim_number WHERE claim_id = v_claim_id;

    INSERT INTO claim_evidence (claim_id, image_path, caption, uploaded_at)
    VALUES (v_claim_id, p_image1, NULLIF(p_caption1, ''), v_submitted);
    IF TRIM(IFNULL(p_image2, '')) <> '' THEN
      INSERT INTO claim_evidence (claim_id, image_path, caption, uploaded_at)
      VALUES (v_claim_id, p_image2, NULLIF(p_caption2, ''), v_submitted);
    END IF;
    IF TRIM(IFNULL(p_image3, '')) <> '' THEN
      INSERT INTO claim_evidence (claim_id, image_path, caption, uploaded_at)
      VALUES (v_claim_id, p_image3, NULLIF(p_caption3, ''), v_submitted);
    END IF;
  COMMIT;

  SELECT 'SUCCESS' AS status,
         CONCAT('Claim ', v_claim_number, ' has been submitted. Our claims team will contact you if further information is needed.') AS message,
         v_claim_id AS claim_id, v_claim_number AS claim_number;
END $$
DELIMITER ;

-- D6) Staff decision. The triggers do the heavy lifting:
--     trg_claim_before_update (rules) -> trg_claim_after_update (deduct)
--     -> trg_claim_after_update_audit (audit row)
DROP PROCEDURE IF EXISTS sp_review_claim;
DELIMITER $$
CREATE PROCEDURE sp_review_claim(
  IN p_claim_id INT,
  IN p_staff_id INT,
  IN p_decision VARCHAR(20),
  IN p_approved_amount DECIMAL(12,2),
  IN p_note VARCHAR(255),
  IN p_reviewed_at DATETIME
)
proc_review: BEGIN
  DECLARE v_role VARCHAR(20);
  DECLARE v_status VARCHAR(20);
  DECLARE v_policy_id INT;
  DECLARE v_number VARCHAR(20);
  DECLARE v_remaining DECIMAL(12,2);
  DECLARE v_found INT DEFAULT 1;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_found = 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SELECT r.role_code INTO v_role
    FROM app_user u
    INNER JOIN role r ON u.role_id = r.role_id
    WHERE u.user_id = p_staff_id;
  IF v_found = 0 OR v_role NOT IN ('STAFF', 'ADMIN') THEN
    SELECT 'ERROR' AS status, 'Only claims officers can assess claims.' AS message, NULL AS remaining_coverage;
    LEAVE proc_review;
  END IF;

  SELECT claim_status, policy_id, claim_number INTO v_status, v_policy_id, v_number
    FROM claim WHERE claim_id = p_claim_id;
  IF v_found = 0 THEN
    SELECT 'ERROR' AS status, 'Claim not found.' AS message, NULL AS remaining_coverage;
    LEAVE proc_review;
  END IF;
  IF v_status <> 'Pending' THEN
    SELECT 'ERROR' AS status, CONCAT('Claim ', v_number, ' has already been ', IF(v_status = 'Approved', 'approved', 'declined'), '.') AS message, NULL AS remaining_coverage;
    LEAVE proc_review;
  END IF;
  IF p_decision IS NULL OR p_decision NOT IN ('Approved', 'Rejected') THEN
    SELECT 'ERROR' AS status, 'Please select a decision.' AS message, NULL AS remaining_coverage;
    LEAVE proc_review;
  END IF;

  START TRANSACTION;
    UPDATE claim
      SET claim_status = p_decision,
          approved_amount = IF(p_decision = 'Approved', p_approved_amount, NULL),
          reviewed_by = p_staff_id,
          review_note = NULLIF(TRIM(p_note), ''),
          reviewed_at = IFNULL(p_reviewed_at, NOW())
      WHERE claim_id = p_claim_id;
  COMMIT;

  SET v_remaining = (SELECT remaining_coverage FROM policy WHERE policy_id = v_policy_id);
  SELECT 'SUCCESS' AS status,
         CONCAT('Claim ', v_number, ' has been ', IF(p_decision = 'Approved', 'approved', 'declined'), '. Remaining benefit on the policy: ',
                FORMAT(v_remaining, 2), ' THB.') AS message,
         v_remaining AS remaining_coverage;
END $$
DELIMITER ;

-- D7) Cancel within the 14-day free-look period: policy + refund together
DROP PROCEDURE IF EXISTS sp_cancel_policy;
DELIMITER $$
CREATE PROCEDURE sp_cancel_policy(
  IN p_policy_id INT,
  IN p_user_id INT
)
proc_cancel: BEGIN
  DECLARE v_owner INT;
  DECLARE v_status VARCHAR(20);
  DECLARE v_created DATETIME;
  DECLARE v_number VARCHAR(20);
  DECLARE v_claims INT;
  DECLARE v_found INT DEFAULT 1;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_found = 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SELECT user_id,
         fn_policy_live_status(policy_status, start_date, end_date, remaining_coverage, CURDATE()),
         created_at, policy_number
    INTO v_owner, v_status, v_created, v_number
    FROM policy WHERE policy_id = p_policy_id;

  IF v_found = 0 OR v_owner <> p_user_id THEN
    SELECT 'ERROR' AS status, 'Policy not found for this account.' AS message;
    LEAVE proc_cancel;
  END IF;
  IF v_status NOT IN ('Active', 'Scheduled') THEN
    SELECT 'ERROR' AS status, 'Only Active or Scheduled policies can be cancelled.' AS message;
    LEAVE proc_cancel;
  END IF;
  IF DATEDIFF(CURDATE(), DATE(v_created)) > 14 THEN
    SELECT 'ERROR' AS status, 'The 14-day free-look period has ended, so this policy can no longer be cancelled online.' AS message;
    LEAVE proc_cancel;
  END IF;
  SET v_claims = (SELECT COUNT(*) FROM claim WHERE policy_id = p_policy_id);
  IF v_claims > 0 THEN
    SELECT 'ERROR' AS status, 'Policies with submitted claims cannot be cancelled.' AS message;
    LEAVE proc_cancel;
  END IF;

  START TRANSACTION;
    UPDATE policy SET policy_status = 'Cancelled', cancelled_at = NOW() WHERE policy_id = p_policy_id;
    UPDATE payment SET payment_status = 'Refunded', refunded_at = NOW()
      WHERE policy_id = p_policy_id AND payment_status = 'Paid';
  COMMIT;

  SELECT 'SUCCESS' AS status,
         CONCAT('Policy ', v_number, ' has been cancelled and your premium will be refunded in full.') AS message;
END $$
DELIMITER ;

-- D8) Persist status transitions (called at sign-in and on the dashboard).
--     "policy_id > 0" keeps MySQL Workbench Safe Update mode happy.
DROP PROCEDURE IF EXISTS sp_refresh_policy_status;
DELIMITER $$
CREATE PROCEDURE sp_refresh_policy_status()
BEGIN
  DECLARE v_policies INT DEFAULT 0;
  DECLARE v_quotes INT DEFAULT 0;

  UPDATE policy
    SET policy_status = fn_policy_live_status(policy_status, start_date, end_date, remaining_coverage, CURDATE())
    WHERE policy_id > 0
      AND policy_status <> 'Cancelled'
      AND policy_status <> fn_policy_live_status(policy_status, start_date, end_date, remaining_coverage, CURDATE());
  SET v_policies = ROW_COUNT();

  UPDATE premium_quote
    SET quote_status = 'Expired'
    WHERE quote_id > 0
      AND quote_status = 'Open'
      AND expires_at < NOW();
  SET v_quotes = ROW_COUNT();

  SELECT 'SUCCESS' AS status, v_policies AS policies_updated, v_quotes AS quotes_expired;
END $$
DELIMITER ;

-- D9) Customer portal list (same idea as Lab 14 getorderdetail)
DROP PROCEDURE IF EXISTS sp_get_my_policies;
DELIMITER $$
CREATE PROCEDURE sp_get_my_policies(
  IN p_user_id INT
)
BEGIN
  SELECT *
  FROM vw_policy_overview
  WHERE user_id = p_user_id
  ORDER BY FIELD(live_status, 'Active', 'Scheduled', 'Exhausted', 'Expired', 'Cancelled'),
           start_date DESC;
END $$
DELIMITER ;

-- D10) Staff claim queue ('Pending' first-in-first-out, or any status / 'All')
DROP PROCEDURE IF EXISTS sp_get_claim_queue;
DELIMITER $$
CREATE PROCEDURE sp_get_claim_queue(
  IN p_status VARCHAR(20)
)
BEGIN
  IF p_status IS NULL OR p_status = 'All' THEN
    SELECT * FROM vw_claim_details
    ORDER BY FIELD(claim_status, 'Pending', 'Approved', 'Rejected'), submitted_at DESC;
  ELSEIF p_status = 'Pending' THEN
    SELECT * FROM vw_claim_details WHERE claim_status = 'Pending' ORDER BY submitted_at ASC;
  ELSE
    SELECT * FROM vw_claim_details WHERE claim_status = p_status ORDER BY reviewed_at DESC;
  END IF;
END $$
DELIMITER ;

-- D11) Dashboard KPI row (scalar subqueries, Lab 7)
DROP PROCEDURE IF EXISTS sp_dashboard_kpis;
DELIMITER $$
CREATE PROCEDURE sp_dashboard_kpis()
BEGIN
  SELECT
    (SELECT IFNULL(SUM(amount), 0) FROM payment WHERE payment_status = 'Paid') AS net_premium,
    (SELECT IFNULL(SUM(amount), 0) FROM payment WHERE payment_status = 'Refunded') AS total_refunded,
    (SELECT COUNT(*) FROM policy WHERE policy_status <> 'Cancelled') AS policies_sold,
    (SELECT COUNT(*) FROM policy WHERE policy_status = 'Active') AS active_policies,
    (SELECT COUNT(*) FROM app_user u INNER JOIN role r ON u.role_id = r.role_id
      WHERE r.role_code = 'CUSTOMER') AS customers,
    (SELECT IFNULL(SUM(approved_amount), 0) FROM claim WHERE claim_status = 'Approved') AS total_payout,
    (SELECT COUNT(*) FROM claim) AS total_claims,
    (SELECT COUNT(*) FROM claim WHERE claim_status = 'Pending') AS pending_claims,
    (SELECT COUNT(*) FROM underwriting_application WHERE app_status = 'Pending') AS pending_applications,
    (SELECT ROUND(SUM(app_status = 'Approved') / NULLIF(SUM(app_status <> 'Pending'), 0) * 100, 1)
       FROM underwriting_application) AS application_approval_pct,
    (SELECT ROUND(AVG(TIMESTAMPDIFF(HOUR, submitted_at, reviewed_at)), 1)
       FROM claim WHERE reviewed_at IS NOT NULL) AS avg_review_hours,
    (SELECT ROUND(SUM(result = 'SUCCESS') / COUNT(*) * 100, 1) FROM checkout_log) AS checkout_success_pct,
    ROUND((SELECT IFNULL(SUM(approved_amount), 0) FROM claim WHERE claim_status = 'Approved')
          / NULLIF((SELECT SUM(amount) FROM payment WHERE payment_status = 'Paid'), 0) * 100, 1) AS loss_ratio_pct;
END $$
DELIMITER ;

-- D12) Product catalog for the public site (only active products)
DROP PROCEDURE IF EXISTS sp_get_catalog;
DELIMITER $$
CREATE PROCEDURE sp_get_catalog(
  IN p_category VARCHAR(40)
)
BEGIN
  SELECT *
  FROM vw_catalog
  WHERE is_active = 1
    AND tier_count > 0
    AND (p_category IS NULL OR p_category = '' OR category = p_category)
  ORDER BY policies_sold DESC, product_name;
END $$
DELIMITER ;

-- D13) Submit an underwriting application + documents in ONE transaction.
--      A copy of the ID card and a proof of occupation are mandatory;
--      the third document is optional (payslip, medical check-up ...).
DROP PROCEDURE IF EXISTS sp_submit_application;
DELIMITER $$
CREATE PROCEDURE sp_submit_application(
  IN p_user_id INT,
  IN p_quote_id INT,
  IN p_occupation VARCHAR(100),
  IN p_employer VARCHAR(120),
  IN p_monthly_income VARCHAR(30),
  IN p_is_smoker TINYINT,
  IN p_has_medical_history TINYINT,
  IN p_health_details VARCHAR(500),
  IN p_id_path VARCHAR(255), IN p_id_caption VARCHAR(160),
  IN p_occupation_path VARCHAR(255), IN p_occupation_caption VARCHAR(160),
  IN p_extra_type VARCHAR(20), IN p_extra_path VARCHAR(255), IN p_extra_caption VARCHAR(160),
  IN p_submitted_at DATETIME
)
proc_application: BEGIN
  DECLARE v_application_id INT;
  DECLARE v_number VARCHAR(20);
  DECLARE v_submitted DATETIME;
  DECLARE EXIT HANDLER FOR 1062
  BEGIN
    ROLLBACK;
    SELECT 'ERROR' AS status, 'An application has already been submitted for this quotation.' AS message,
           NULL AS application_id, NULL AS application_number;
  END;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;   -- trigger and CHECK messages reach Django
  END;

  SET v_submitted = IFNULL(p_submitted_at, NOW());

  IF TRIM(IFNULL(p_id_path, '')) = '' OR TRIM(IFNULL(p_occupation_path, '')) = '' THEN
    SELECT 'ERROR' AS status, 'Please attach a copy of your ID card and a proof of occupation.' AS message,
           NULL AS application_id, NULL AS application_number;
    LEAVE proc_application;
  END IF;

  START TRANSACTION;
    INSERT INTO underwriting_application (quote_id, user_id, occupation, employer, monthly_income,
                                          is_smoker, has_medical_history, health_details, submitted_at)
    VALUES (p_quote_id, p_user_id, p_occupation, NULLIF(TRIM(p_employer), ''), p_monthly_income,
            IFNULL(p_is_smoker, 0), IFNULL(p_has_medical_history, 0), NULLIF(TRIM(p_health_details), ''), v_submitted);

    SET v_application_id = LAST_INSERT_ID();
    SET v_number = fn_format_number('APP', v_application_id, DATE(v_submitted));
    UPDATE underwriting_application SET application_number = v_number WHERE application_id = v_application_id;

    INSERT INTO application_document (application_id, document_type, image_path, caption, uploaded_at)
    VALUES (v_application_id, 'Identity', p_id_path, IFNULL(NULLIF(p_id_caption, ''), 'Copy of ID card'), v_submitted);
    INSERT INTO application_document (application_id, document_type, image_path, caption, uploaded_at)
    VALUES (v_application_id, 'Occupation', p_occupation_path,
            IFNULL(NULLIF(p_occupation_caption, ''), 'Proof of occupation'), v_submitted);
    IF TRIM(IFNULL(p_extra_path, '')) <> '' THEN
      INSERT INTO application_document (application_id, document_type, image_path, caption, uploaded_at)
      VALUES (v_application_id, IFNULL(NULLIF(p_extra_type, ''), 'Other'), p_extra_path, NULLIF(p_extra_caption, ''), v_submitted);
    END IF;
  COMMIT;

  SELECT 'SUCCESS' AS status,
         CONCAT('Application ', v_number, ' has been submitted. Our underwriting team will review it, usually within one working day.') AS message,
         v_application_id AS application_id, v_number AS application_number;
END $$
DELIMITER ;

-- D14) Officer decision on an application. trg_application_before_update
--      checks the rules, trg_application_after_update opens the 7-day
--      payment window (Approved) or closes the quotation (Rejected).
DROP PROCEDURE IF EXISTS sp_review_application;
DELIMITER $$
CREATE PROCEDURE sp_review_application(
  IN p_application_id INT,
  IN p_staff_id INT,
  IN p_decision VARCHAR(20),
  IN p_note VARCHAR(255),
  IN p_reviewed_at DATETIME
)
proc_review_application: BEGIN
  DECLARE v_status VARCHAR(20);
  DECLARE v_number VARCHAR(20);
  DECLARE v_found INT DEFAULT 1;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_found = 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SELECT app_status, application_number INTO v_status, v_number
    FROM underwriting_application WHERE application_id = p_application_id;
  IF v_found = 0 THEN
    SELECT 'ERROR' AS status, 'Application not found.' AS message;
    LEAVE proc_review_application;
  END IF;
  IF v_status <> 'Pending' THEN
    SELECT 'ERROR' AS status, CONCAT('Application ', v_number, ' has already been ',
           IF(v_status = 'Approved', 'approved', 'declined'), '.') AS message;
    LEAVE proc_review_application;
  END IF;
  IF p_decision IS NULL OR p_decision NOT IN ('Approved', 'Rejected') THEN
    SELECT 'ERROR' AS status, 'Please select a decision.' AS message;
    LEAVE proc_review_application;
  END IF;

  START TRANSACTION;
    UPDATE underwriting_application
      SET app_status = p_decision,
          reviewed_by = p_staff_id,
          review_note = NULLIF(TRIM(p_note), ''),
          reviewed_at = IFNULL(p_reviewed_at, NOW())
      WHERE application_id = p_application_id;
  COMMIT;

  SELECT 'SUCCESS' AS status,
         IF(p_decision = 'Approved',
            CONCAT('Application ', v_number, ' has been approved. The customer has 7 days to complete payment.'),
            CONCAT('Application ', v_number, ' has been declined.')) AS message;
END $$
DELIMITER ;

-- D15) Officer queue for applications ('Pending' oldest first, or any status / 'All')
DROP PROCEDURE IF EXISTS sp_get_application_queue;
DELIMITER $$
CREATE PROCEDURE sp_get_application_queue(
  IN p_status VARCHAR(20)
)
BEGIN
  IF p_status IS NULL OR p_status = 'All' THEN
    SELECT * FROM vw_application_details
    ORDER BY FIELD(app_status, 'Pending', 'Approved', 'Rejected'), submitted_at DESC;
  ELSEIF p_status = 'Pending' THEN
    SELECT * FROM vw_application_details WHERE app_status = 'Pending' ORDER BY submitted_at ASC;
  ELSE
    SELECT * FROM vw_application_details WHERE app_status = p_status ORDER BY reviewed_at DESC;
  END IF;
END $$
DELIMITER ;

-- Quick check (Slides 6-8): list everything we just created
SELECT ROUTINE_TYPE, ROUTINE_NAME FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = 'bibdb' ORDER BY ROUTINE_TYPE, ROUTINE_NAME;
SELECT TRIGGER_NAME, ACTION_TIMING, EVENT_MANIPULATION, EVENT_OBJECT_TABLE
FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = 'bibdb' ORDER BY EVENT_OBJECT_TABLE, ACTION_ORDER;
SHOW FULL TABLES WHERE Table_type = 'VIEW';
