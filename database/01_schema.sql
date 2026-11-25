-- =====================================================================
--  BIB Assurance (Bangkok Insurance & Benefits)
--  "Trusted Protection for Every Stage of Life"
--  2603491 Database Programming - Final Group Project
--  Script 1 of 3 : 01_schema.sql
--  Creates the bibdb schema, all 15 tables, keys, CHECK constraints
--  and indexes.  Run in MySQL Workbench (MySQL 8.0.16+).
--
--  Run order : 01_schema.sql  ->  02_routines.sql  ->  03_seed_data.sql
--  WARNING   : this script DROPS and re-creates bibdb (Lab 2 / Lab 3 style).
--              Re-run "python manage.py migrate" afterwards so Django can
--              re-create its own session/admin tables.
-- =====================================================================

DROP DATABASE IF EXISTS bibdb;
CREATE DATABASE bibdb
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE bibdb;

-- ---------------------------------------------------------------------
-- 1) role : CUSTOMER / STAFF / ADMIN                       (Module 1)
-- ---------------------------------------------------------------------
CREATE TABLE role (
  role_id    INT          NOT NULL AUTO_INCREMENT,
  role_code  VARCHAR(20)  NOT NULL,
  role_name  VARCHAR(50)  NOT NULL,
  PRIMARY KEY (role_id),
  UNIQUE KEY role_code_UNIQUE (role_code),
  CONSTRAINT check_role_code CHECK (role_code IN ('CUSTOMER', 'STAFF', 'ADMIN'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 2) app_user : every person who can sign in               (Module 1)
--    password_hash stores Django's make_password() output (never plain text)
--    18+ rule for customers lives in trigger trg_app_user_before_insert
--    because a CHECK constraint cannot call CURDATE().
-- ---------------------------------------------------------------------
CREATE TABLE app_user (
  user_id        INT           NOT NULL AUTO_INCREMENT,
  role_id        INT           NOT NULL,
  email          VARCHAR(120)  NOT NULL,
  password_hash  VARCHAR(255)  NOT NULL,
  first_name     VARCHAR(60)   NOT NULL,
  last_name      VARCHAR(60)   NOT NULL,
  phone          VARCHAR(20)   NULL,
  date_of_birth  DATE          NULL,
  avatar_path    VARCHAR(255)  NULL,
  is_active      TINYINT(1)    NOT NULL DEFAULT 1,
  created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at  DATETIME      NULL,
  PRIMARY KEY (user_id),
  UNIQUE KEY email_UNIQUE (email),
  KEY FK_user_role_idx (role_id),
  CONSTRAINT FK_user_role FOREIGN KEY (role_id) REFERENCES role (role_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT check_user_email  CHECK (email LIKE '%_@_%._%'),
  CONSTRAINT check_user_active CHECK (is_active IN (0, 1)),
  CONSTRAINT check_user_dob    CHECK (date_of_birth IS NULL OR date_of_birth >= '1900-01-01')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 3) product : insurance plans (health, critical illness, life, PA, retirement)  (Module 2)
-- ---------------------------------------------------------------------
CREATE TABLE product (
  product_id            INT           NOT NULL AUTO_INCREMENT,
  product_code          VARCHAR(20)   NOT NULL,
  product_name          VARCHAR(100)  NOT NULL,
  tagline               VARCHAR(160)  NOT NULL,
  description           TEXT          NOT NULL,
  category              VARCHAR(40)   NOT NULL,
  thumbnail_path        VARCHAR(255)  NULL,
  requires_beneficiary  TINYINT(1)    NOT NULL DEFAULT 0,
  is_active             TINYINT(1)    NOT NULL DEFAULT 1,
  created_at            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (product_id),
  UNIQUE KEY product_code_UNIQUE (product_code),
  UNIQUE KEY product_name_UNIQUE (product_name),
  CONSTRAINT check_product_category CHECK (category IN ('Health', 'Critical Illness', 'Life', 'Personal Accident', 'Retirement')),
  CONSTRAINT check_product_flags    CHECK (requires_beneficiary IN (0, 1) AND is_active IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 4) coverage_tier : 3 tiers per product                   (Module 2)
--    base_annual_premium = 12-month price at min_coverage for a
--    "Standard" applicant aged 25-39 (all multipliers = 1.000)
-- ---------------------------------------------------------------------
CREATE TABLE coverage_tier (
  tier_id              INT               NOT NULL AUTO_INCREMENT,
  product_id           INT               NOT NULL,
  tier_name            VARCHAR(50)       NOT NULL,
  tier_level           TINYINT           NOT NULL,
  min_coverage         DECIMAL(12,2)     NOT NULL,
  max_coverage         DECIMAL(12,2)     NOT NULL,
  base_annual_premium  DECIMAL(10,2)     NOT NULL,
  deductible           DECIMAL(10,2)     NOT NULL DEFAULT 0.00,
  duration_months      TINYINT UNSIGNED  NOT NULL DEFAULT 12,
  perks                VARCHAR(255)      NULL,
  PRIMARY KEY (tier_id),
  UNIQUE KEY product_tier_UNIQUE (product_id, tier_name),
  UNIQUE KEY product_level_UNIQUE (product_id, tier_level),
  CONSTRAINT FK_tier_product FOREIGN KEY (product_id) REFERENCES product (product_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT check_tier_level      CHECK (tier_level BETWEEN 1 AND 5),
  CONSTRAINT check_tier_coverage   CHECK (min_coverage > 0 AND min_coverage <= max_coverage),
  CONSTRAINT check_tier_premium    CHECK (base_annual_premium > 0),
  CONSTRAINT check_tier_deductible CHECK (deductible >= 0 AND deductible < min_coverage),
  CONSTRAINT check_tier_duration   CHECK (duration_months BETWEEN 1 AND 24)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 5) premium_factor : rating rules for fn_calc_premium     (Module 2)
--    product_id NULL = global default, otherwise a product override
-- ---------------------------------------------------------------------
CREATE TABLE premium_factor (
  factor_id    INT                   NOT NULL AUTO_INCREMENT,
  product_id   INT                   NULL,
  factor_type  ENUM('AGE', 'RISK')   NOT NULL,
  range_min    SMALLINT              NOT NULL,
  range_max    SMALLINT              NOT NULL,
  multiplier   DECIMAL(5,3)          NOT NULL,
  label        VARCHAR(60)           NOT NULL,
  PRIMARY KEY (factor_id),
  KEY FK_factor_product_idx (product_id),
  CONSTRAINT FK_factor_product FOREIGN KEY (product_id) REFERENCES product (product_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT check_factor_range      CHECK (range_min <= range_max),
  CONSTRAINT check_factor_multiplier CHECK (multiplier > 0 AND multiplier <= 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 6) premium_quote : server-side quote, valid 7 days        (Module 2/3)
--    Checkout always charges quoted_premium, so the browser can never
--    send its own price.
-- ---------------------------------------------------------------------
CREATE TABLE premium_quote (
  quote_id         INT                                     NOT NULL AUTO_INCREMENT,
  user_id          INT                                     NOT NULL,
  tier_id          INT                                     NOT NULL,
  coverage_amount  DECIMAL(12,2)                           NOT NULL,
  insured_age      TINYINT UNSIGNED                        NOT NULL,
  risk_level       TINYINT UNSIGNED                        NOT NULL,
  age_multiplier   DECIMAL(5,3)                            NOT NULL,
  risk_multiplier  DECIMAL(5,3)                            NOT NULL,
  quoted_premium   DECIMAL(10,2)                           NOT NULL,
  quote_status     ENUM('Open', 'Converted', 'Expired', 'Declined') NOT NULL DEFAULT 'Open',
  created_at       DATETIME                                NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at       DATETIME                                NOT NULL,
  PRIMARY KEY (quote_id),
  KEY FK_quote_tier_idx (tier_id),
  KEY idx_quote_user_created (user_id, created_at),
  CONSTRAINT FK_quote_user FOREIGN KEY (user_id) REFERENCES app_user (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT FK_quote_tier FOREIGN KEY (tier_id) REFERENCES coverage_tier (tier_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT check_quote_coverage CHECK (coverage_amount > 0),
  CONSTRAINT check_quote_age      CHECK (insured_age BETWEEN 18 AND 120),
  CONSTRAINT check_quote_risk     CHECK (risk_level BETWEEN 1 AND 4),
  CONSTRAINT check_quote_premium  CHECK (quoted_premium > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 7) policy : an issued insurance policy                   (Module 3/4)
--    remaining_coverage is reduced by trigger trg_claim_after_update
-- ---------------------------------------------------------------------
CREATE TABLE policy (
  policy_id           INT            NOT NULL AUTO_INCREMENT,
  policy_number       VARCHAR(20)    NULL,
  user_id             INT            NOT NULL,
  tier_id             INT            NOT NULL,
  quote_id            INT            NULL,
  coverage_amount     DECIMAL(12,2)  NOT NULL,
  remaining_coverage  DECIMAL(12,2)  NOT NULL,
  premium_amount      DECIMAL(10,2)  NOT NULL,
  start_date          DATE           NOT NULL,
  end_date            DATE           NOT NULL,
  policy_status       ENUM('Scheduled', 'Active', 'Expired', 'Exhausted', 'Cancelled') NOT NULL DEFAULT 'Active',
  created_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  cancelled_at        DATETIME       NULL,
  PRIMARY KEY (policy_id),
  UNIQUE KEY policy_number_UNIQUE (policy_number),
  UNIQUE KEY policy_quote_UNIQUE (quote_id),
  KEY FK_policy_tier_idx (tier_id),
  KEY idx_policy_user_status (user_id, policy_status),
  KEY idx_policy_end_date (end_date),
  CONSTRAINT FK_policy_user FOREIGN KEY (user_id) REFERENCES app_user (user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT FK_policy_tier FOREIGN KEY (tier_id) REFERENCES coverage_tier (tier_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT FK_policy_quote FOREIGN KEY (quote_id) REFERENCES premium_quote (quote_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT check_policy_dates     CHECK (end_date > start_date),
  CONSTRAINT check_policy_coverage  CHECK (coverage_amount > 0),
  CONSTRAINT check_policy_remaining CHECK (remaining_coverage >= 0 AND remaining_coverage <= coverage_amount),
  CONSTRAINT check_policy_premium   CHECK (premium_amount > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 8) payment : mock payment, only the last 4 card digits    (Module 3)
-- ---------------------------------------------------------------------
CREATE TABLE payment (
  payment_id       INT                                        NOT NULL AUTO_INCREMENT,
  policy_id        INT                                        NOT NULL,
  user_id          INT                                        NOT NULL,
  amount           DECIMAL(10,2)                              NOT NULL,
  payment_method   ENUM('Card', 'PromptPay', 'BankTransfer')  NOT NULL,
  card_last4       CHAR(4)                                    NULL,
  payment_status   ENUM('Paid', 'Refunded')                   NOT NULL DEFAULT 'Paid',
  transaction_ref  VARCHAR(40)                                NOT NULL,
  paid_at          DATETIME                                   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  refunded_at      DATETIME                                   NULL,
  PRIMARY KEY (payment_id),
  UNIQUE KEY transaction_ref_UNIQUE (transaction_ref),
  KEY FK_payment_policy_idx (policy_id),
  KEY FK_payment_user_idx (user_id),
  KEY idx_payment_paid_at (paid_at),
  CONSTRAINT FK_payment_policy FOREIGN KEY (policy_id) REFERENCES policy (policy_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT FK_payment_user FOREIGN KEY (user_id) REFERENCES app_user (user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT check_payment_amount CHECK (amount > 0),
  CONSTRAINT check_payment_card   CHECK ((payment_method = 'Card' AND card_last4 REGEXP '^[0-9]{4}$')
                                      OR (payment_method <> 'Card' AND card_last4 IS NULL)),
  CONSTRAINT check_payment_refund CHECK ((payment_status = 'Refunded' AND refunded_at IS NOT NULL)
                                      OR (payment_status = 'Paid' AND refunded_at IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 9) checkout_log : every checkout attempt, incl. ROLLBACKs (Module 3)
--    Written AFTER the ROLLBACK, so declined attempts are still visible.
-- ---------------------------------------------------------------------
CREATE TABLE checkout_log (
  log_id          INT                                   NOT NULL AUTO_INCREMENT,
  user_id         INT                                   NOT NULL,
  quote_id        INT                                   NULL,
  policy_id       INT                                   NULL,
  amount          DECIMAL(10,2)                         NULL,
  payment_method  VARCHAR(20)                           NULL,
  card_last4      CHAR(4)                               NULL,
  result          ENUM('SUCCESS', 'DECLINED', 'ERROR')  NOT NULL,
  message         VARCHAR(255)                          NOT NULL,
  attempted_at    DATETIME                              NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (log_id),
  KEY FK_log_user_idx (user_id),
  KEY FK_log_quote_idx (quote_id),
  KEY FK_log_policy_idx (policy_id),
  KEY idx_log_result_time (result, attempted_at),
  CONSTRAINT FK_log_user FOREIGN KEY (user_id) REFERENCES app_user (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT FK_log_quote FOREIGN KEY (quote_id) REFERENCES premium_quote (quote_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT FK_log_policy FOREIGN KEY (policy_id) REFERENCES policy (policy_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 10) policy_beneficiary : who receives the payout          (Module 1)
--     max 4 per policy and running total <= 100% enforced by triggers;
--     "exactly 100%" enforced by sp_save_beneficiaries (transaction).
-- ---------------------------------------------------------------------
CREATE TABLE policy_beneficiary (
  beneficiary_id  INT           NOT NULL AUTO_INCREMENT,
  policy_id       INT           NOT NULL,
  full_name       VARCHAR(120)  NOT NULL,
  relationship    VARCHAR(40)   NOT NULL,
  allocation_pct  DECIMAL(5,2)  NOT NULL,
  created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (beneficiary_id),
  UNIQUE KEY policy_beneficiary_UNIQUE (policy_id, full_name),
  CONSTRAINT FK_beneficiary_policy FOREIGN KEY (policy_id) REFERENCES policy (policy_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT check_beneficiary_pct CHECK (allocation_pct > 0 AND allocation_pct <= 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 11) claim : customer claims                               (Module 5)
-- ---------------------------------------------------------------------
CREATE TABLE claim (
  claim_id              INT                                       NOT NULL AUTO_INCREMENT,
  claim_number          VARCHAR(20)                               NULL,
  policy_id             INT                                       NOT NULL,
  incident_date         DATE                                      NOT NULL,
  incident_title        VARCHAR(120)                              NOT NULL,
  incident_description  TEXT                                      NOT NULL,
  claimed_amount        DECIMAL(12,2)                             NOT NULL,
  approved_amount       DECIMAL(12,2)                             NULL,
  claim_status          ENUM('Pending', 'Approved', 'Rejected')   NOT NULL DEFAULT 'Pending',
  reviewed_by           INT                                       NULL,
  review_note           VARCHAR(255)                              NULL,
  submitted_at          DATETIME                                  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at           DATETIME                                  NULL,
  PRIMARY KEY (claim_id),
  UNIQUE KEY claim_number_UNIQUE (claim_number),
  KEY FK_claim_policy_idx (policy_id),
  KEY FK_claim_reviewer_idx (reviewed_by),
  KEY idx_claim_status_submitted (claim_status, submitted_at),
  CONSTRAINT FK_claim_policy FOREIGN KEY (policy_id) REFERENCES policy (policy_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT FK_claim_reviewer FOREIGN KEY (reviewed_by) REFERENCES app_user (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT check_claim_amount   CHECK (claimed_amount > 0),
  CONSTRAINT check_claim_approved CHECK (approved_amount IS NULL OR (approved_amount > 0 AND approved_amount <= claimed_amount)),
  CONSTRAINT check_claim_decision CHECK ((claim_status = 'Approved' AND approved_amount IS NOT NULL)
                                      OR (claim_status <> 'Approved' AND approved_amount IS NULL)),
  CONSTRAINT check_claim_review_time CHECK (reviewed_at IS NULL OR reviewed_at >= submitted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 12) claim_evidence : photo evidence, path into MEDIA_ROOT (Module 5)
-- ---------------------------------------------------------------------
CREATE TABLE claim_evidence (
  evidence_id  INT           NOT NULL AUTO_INCREMENT,
  claim_id     INT           NOT NULL,
  image_path   VARCHAR(255)  NOT NULL,
  caption      VARCHAR(160)  NULL,
  uploaded_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (evidence_id),
  KEY FK_evidence_claim_idx (claim_id),
  CONSTRAINT FK_evidence_claim FOREIGN KEY (claim_id) REFERENCES claim (claim_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 13) claim_status_audit : written only by triggers (Lab 9 audit pattern)
-- ---------------------------------------------------------------------
CREATE TABLE claim_status_audit (
  audit_id          INT            NOT NULL AUTO_INCREMENT,
  claim_id          INT            NOT NULL,
  policy_id         INT            NOT NULL,
  old_status        VARCHAR(20)    NULL,
  new_status        VARCHAR(20)    NOT NULL,
  amount            DECIMAL(12,2)  NULL,
  remaining_before  DECIMAL(12,2)  NULL,
  remaining_after   DECIMAL(12,2)  NULL,
  changed_by        INT            NULL,
  actiontype        VARCHAR(50)    NOT NULL,
  changedate        DATETIME       NOT NULL,
  PRIMARY KEY (audit_id),
  KEY FK_audit_claim_idx (claim_id),
  KEY idx_audit_policy (policy_id),
  CONSTRAINT FK_audit_claim FOREIGN KEY (claim_id) REFERENCES claim (claim_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 14) underwriting_application : before a quotation can be paid, the
--     customer submits an application (occupation + health declaration)
--     that a claims officer approves or declines.            (Module 3)
--     One application per quotation (UNIQUE quote_id).
--     Rules that need other tables (quote still valid, reviewer is staff,
--     decision is final) live in triggers - see 02_routines.sql.
--     reviewed_by has ON DELETE SET NULL, so it cannot be used in a CHECK.
-- ---------------------------------------------------------------------
CREATE TABLE underwriting_application (
  application_id      INT                                       NOT NULL AUTO_INCREMENT,
  application_number  VARCHAR(20)                               NULL,
  quote_id            INT                                       NOT NULL,
  user_id             INT                                       NOT NULL,
  occupation          VARCHAR(100)                              NOT NULL,
  employer            VARCHAR(120)                              NULL,
  monthly_income      VARCHAR(30)                               NOT NULL,
  is_smoker           TINYINT                                   NOT NULL DEFAULT 0,
  has_medical_history TINYINT                                   NOT NULL DEFAULT 0,
  health_details      VARCHAR(500)                              NULL,
  app_status          ENUM('Pending', 'Approved', 'Rejected')   NOT NULL DEFAULT 'Pending',
  reviewed_by         INT                                       NULL,
  review_note         VARCHAR(255)                              NULL,
  submitted_at        DATETIME                                  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at         DATETIME                                  NULL,
  PRIMARY KEY (application_id),
  UNIQUE KEY application_number_UNIQUE (application_number),
  UNIQUE KEY application_quote_UNIQUE (quote_id),
  KEY FK_application_user_idx (user_id),
  KEY FK_application_reviewer_idx (reviewed_by),
  KEY idx_application_status_submitted (app_status, submitted_at),
  CONSTRAINT FK_application_quote FOREIGN KEY (quote_id) REFERENCES premium_quote (quote_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT FK_application_user FOREIGN KEY (user_id) REFERENCES app_user (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT FK_application_reviewer FOREIGN KEY (reviewed_by) REFERENCES app_user (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT check_application_flags  CHECK (is_smoker IN (0, 1) AND has_medical_history IN (0, 1)),
  CONSTRAINT check_application_income CHECK (monthly_income IN ('Below 15,000', '15,000-30,000', '30,001-50,000',
                                                                '50,001-100,000', 'Above 100,000')),
  CONSTRAINT check_application_health CHECK (has_medical_history = 0
                                             OR (health_details IS NOT NULL AND CHAR_LENGTH(health_details) >= 5)),
  CONSTRAINT check_application_review_time CHECK (reviewed_at IS NULL OR reviewed_at >= submitted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 15) application_document : ID card, proof of occupation, payslip,
--     medical check-up ... (LabExtra: only the file path is stored)
-- ---------------------------------------------------------------------
CREATE TABLE application_document (
  document_id     INT                                                          NOT NULL AUTO_INCREMENT,
  application_id  INT                                                          NOT NULL,
  document_type   ENUM('Identity', 'Occupation', 'Income', 'Medical', 'Other') NOT NULL,
  image_path      VARCHAR(255)                                                 NOT NULL,
  caption         VARCHAR(160)                                                 NULL,
  uploaded_at     DATETIME                                                     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (document_id),
  KEY FK_document_application_idx (application_id),
  CONSTRAINT FK_document_application FOREIGN KEY (application_id) REFERENCES underwriting_application (application_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Quick check (Lab 3 style) - should list 15 tables
SHOW TABLES;
