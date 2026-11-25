"""Generates database/03_seed_data.sql for BIB Assurance (deterministic).

All dates are written relative to CURDATE(), so the data always looks current
on whatever day the script is run. Claims and assessments go through the real
triggers (validation, benefit deduction, audit rows).

Usage (inside projectenv):  python make_seed.py ../03_seed_data.sql
"""
import math
import random
import sys
from datetime import date, timedelta

import django
from django.conf import settings

settings.configure(PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"])
django.setup()
from django.contrib.auth.hashers import make_password  # noqa: E402

OUT = sys.argv[1]
rnd = random.Random(2603491)
TODAY = date(2026, 11, 15)      # only used to reason about month lengths
DEMO_PASSWORD = "Bib@2026"


def q(s):
    return "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'"


def dd(off):
    return f"DATE_ADD(CURDATE(), INTERVAL {off} DAY)"


def dt(off, hhmm):
    return f"TIMESTAMP(DATE_ADD(CURDATE(), INTERVAL {off} DAY), '{hhmm}:00')"


def add_months(d, m):
    y = d.year + (d.month - 1 + m) // 12
    mo = (d.month - 1 + m) % 12 + 1
    day = min(d.day, [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1])
    return date(y, mo, day)


def end_off(start_off, months):
    s = TODAY + timedelta(days=start_off)
    return ((add_months(s, months) - timedelta(days=1)) - TODAY).days


def rtime(lo=8, hi=20):
    return f"{rnd.randint(lo, hi - 1):02d}:{rnd.choice(['05', '12', '18', '24', '31', '37', '42', '48', '53'])}"


# ------------------------------------------------------------------ products
PRODUCTS = [
    (1, "HEALTH", "BIB Health Happy",
     "Lump-sum medical cover for in-patient and out-patient care.",
     "A comprehensive medical plan that pays hospital bills up to your annual limit, covering room and board, "
     "surgery, specialist fees, diagnostic tests and selected out-patient treatment at accredited hospitals "
     "throughout Thailand. Cashless admission is available at our partner hospitals.",
     "Health", "product/bib_health_happy.svg", 0),
    (2, "CI", "BIB CI Super Care",
     "A lump-sum payment on diagnosis of a covered critical illness.",
     "Receive a lump-sum benefit on diagnosis of a covered critical illness, including cancer, heart attack "
     "and stroke, so you can focus on treatment and recovery. The benefit can be used for medical costs, "
     "income replacement or family expenses.",
     "Critical Illness", "product/bib_ci_super_care.svg", 0),
    (3, "LIFE", "BIB Life Protector",
     "Whole life assurance that secures your family's financial future.",
     "Lifelong protection with a guaranteed sum assured paid to your beneficiaries, together with a total and "
     "permanent disability benefit. Cover continues to age 99; premiums are paid annually and each payment "
     "renews your protection for the next policy year.",
     "Life", "product/bib_life_protector.svg", 1),
    (4, "PA", "BIB PA Shield",
     "Accident medical expenses and accidental death or disability cover.",
     "Round-the-clock protection against accidents at home, at work or while travelling. Pays accident medical "
     "expenses and a lump-sum benefit for accidental death or permanent disability to the beneficiaries you "
     "nominate.",
     "Personal Accident", "product/bib_pa_shield.svg", 1),
    (5, "RETIRE", "BIB Smart Retire",
     "Guaranteed retirement income with savings protection.",
     "An annuity plan that builds your retirement fund and pays a guaranteed annual income from your chosen "
     "retirement age until age 85, with a death benefit before retirement. Premiums may qualify for personal "
     "income tax deductions.",
     "Retirement", "product/bib_smart_retire.svg", 0),
]

# tier_id, product_id, name, level, min, max, base, deductible, months, perks
TIERS = [
    (1, 1, "Silver", 1, 1000000, 3000000, 9900, 20000, 12,
     "In-patient annual limit · Room & board up to ฿4,000 per day · ฿20,000 deductible per claim"),
    (2, 1, "Gold", 2, 3000000, 6000000, 31500, 0, 12,
     "In-patient & out-patient · Room & board up to ฿8,000 per day · No deductible"),
    (3, 1, "Platinum", 3, 6000000, 15000000, 66000, 0, 12,
     "Private room · Out-patient & dental · Worldwide emergency treatment"),
    (4, 2, "Essential", 1, 500000, 1500000, 2900, 0, 12,
     "Lump sum on diagnosis of 30 major critical illnesses"),
    (5, 2, "Plus", 2, 1500000, 3000000, 9000, 0, 12,
     "Early, intermediate and severe stages · 70 covered conditions"),
    (6, 2, "Premier", 3, 3000000, 5000000, 18900, 0, 12,
     "Multiple claims up to 170% of sum insured · 170 covered conditions"),
    (7, 3, "Classic", 1, 500000, 2000000, 7500, 0, 12,
     "Death and total & permanent disability benefit"),
    (8, 3, "Prestige", 2, 2000000, 5000000, 31000, 0, 12,
     "Classic benefits plus waiver of premium on disability"),
    (9, 3, "Legacy", 3, 5000000, 20000000, 80000, 0, 12,
     "Prestige benefits plus terminal illness advance and estate planning service"),
    (10, 4, "Shield Basic", 1, 100000, 500000, 650, 0, 12,
     "Accidental death & disability · medical expenses up to ฿20,000 per accident"),
    (11, 4, "Shield Plus", 2, 500000, 1000000, 3400, 0, 12,
     "Medical expenses up to ฿50,000 per accident · daily hospital income"),
    (12, 4, "Shield Max", 3, 1000000, 3000000, 7200, 0, 12,
     "Medical expenses up to ฿100,000 per accident · double benefit on public transport"),
    (13, 5, "Retire 60", 1, 200000, 1000000, 24000, 0, 12,
     "Guaranteed annual income of 15% of sum assured from age 60 to 85"),
    (14, 5, "Retire 55", 2, 1000000, 2000000, 125000, 0, 12,
     "Guaranteed income from age 55 to 85 · death benefit before retirement"),
    (15, 5, "Retire Plus", 3, 2000000, 4000000, 260000, 0, 12,
     "Guaranteed income from age 55 plus an annual bonus"),
]
TIER = {t[0]: t for t in TIERS}
TIERS_OF = {p[0]: [t for t in TIERS if t[1] == p[0]] for p in PRODUCTS}
TIER_WEIGHTS = {1: [55, 32, 13], 2: [55, 32, 13], 3: [60, 30, 10], 4: [50, 35, 15], 5: [75, 20, 5]}
PA_MEDICAL_LIMIT = {10: 20000, 11: 50000, 12: 100000}

FACTORS = [
    (1, None, "AGE", 18, 24, "0.850", "Age 18-24"),
    (2, None, "AGE", 25, 39, "1.000", "Age 25-39"),
    (3, None, "AGE", 40, 59, "1.450", "Age 40-59"),
    (4, None, "AGE", 60, 120, "2.200", "Age 60+"),
    (5, None, "RISK", 1, 1, "0.900", "Preferred"),
    (6, None, "RISK", 2, 2, "1.000", "Standard"),
    (7, None, "RISK", 3, 3, "1.350", "Rated (Class B)"),
    (8, None, "RISK", 4, 4, "1.750", "Rated (Class C)"),
    (9, 2, "AGE", 40, 59, "1.800", "Age 40-59"),
    (10, 2, "AGE", 60, 120, "3.000", "Age 60+"),
    (11, 4, "AGE", 40, 59, "1.100", "Age 40-59"),
    (12, 4, "AGE", 60, 120, "1.300", "Age 60+"),
    (13, 4, "RISK", 1, 1, "0.900", "Occupation class 1"),
    (14, 4, "RISK", 2, 2, "1.000", "Occupation class 2"),
    (15, 4, "RISK", 3, 3, "1.400", "Occupation class 3"),
    (16, 4, "RISK", 4, 4, "1.900", "Occupation class 4"),
    (17, 5, "AGE", 40, 59, "1.150", "Age 40-59"),
    (18, 5, "AGE", 60, 120, "1.300", "Age 60+"),
]

# ------------------------------------------------------------------- users
# id, role(1 admin 2 staff 3 customer), first, last, email, phone, age, avatar, preferred products
USERS = [
    (1, 1, "Siriporn", "Saetang", "admin@bib.test", "02-000-1001", 44, "avatar/siriporn_saetang.svg", None),
    (2, 2, "Pimchanok", "Wongsa", "pim@bib.test", "02-000-1002", 32, "avatar/pimchanok_wongsa.svg", None),
    (3, 2, "Krit", "Chaiyaporn", "krit@bib.test", "02-000-1003", 37, "avatar/krit_chaiyaporn.svg", None),
    (4, 2, "Mintra", "Suksai", "mint@bib.test", "02-000-1004", 29, "avatar/mintra_suksai.svg", None),
    (5, 3, "Somchai", "Jaidee", "somchai@bib.test", "081-234-5601", 41, "avatar/somchai_jaidee.svg", [1, 2, 3]),
    (6, 3, "Fah", "Rattanakul", "fah@bib.test", "081-234-5602", 29, "avatar/fah_rattanakul.svg", [1, 4]),
    (7, 3, "Tawan", "Meesuk", "tawan@bib.test", "081-234-5603", 26, None, []),
    (8, 3, "Arthit", "Boonsong", "arthit@bib.test", "081-234-5604", 34, "avatar/arthit_boonsong.svg", [4, 1]),
    (9, 3, "Chompoo", "Srisuk", "chompoo@bib.test", "081-234-5605", 38, "avatar/chompoo_srisuk.svg", [1, 3, 5]),
    (10, 3, "Daniel", "Carter", "daniel@bib.test", "081-234-5606", 45, "avatar/daniel_carter.svg", [3, 1, 4]),
    (11, 3, "Emi", "Tanaka", "emi@bib.test", "081-234-5607", 31, "avatar/emi_tanaka.svg", [1, 2]),
    (12, 3, "Gun", "Phongphan", "gun@bib.test", "081-234-5608", 52, "avatar/gun_phongphan.svg", [5, 3, 2]),
    (13, 3, "Jenjira", "Kaewmanee", "jenjira@bib.test", "081-234-5609", 27, "avatar/jenjira_kaewmanee.svg", [4, 1]),
    (14, 3, "Lukas", "Becker", "lukas@bib.test", "081-234-5610", 36, "avatar/lukas_becker.svg", [1, 4, 3]),
    (15, 3, "Mali", "Thongdee", "mali@bib.test", "081-234-5611", 58, "avatar/mali_thongdee.svg", [2, 1, 3]),
    (16, 3, "Nok", "Prasert", "nok@bib.test", "081-234-5612", 33, "avatar/nok_prasert.svg", [4, 1, 2]),
    (17, 3, "Priya", "Sharma", "priya@bib.test", "081-234-5613", 30, "avatar/priya_sharma.svg", [1, 3]),
    (18, 3, "Ploy", "Chantra", "ploy@bib.test", "081-234-5614", 24, None, [4, 1]),
    (19, 3, "Beam", "Sirichai", "beam@bib.test", "081-234-5615", 28, None, [1, 4]),
    (20, 3, "Kanokwan", "Detsri", "kanokwan@bib.test", "081-234-5616", 47, None, [2, 3, 1]),
    (21, 3, "Oliver", "Nguyen", "oliver@bib.test", "081-234-5617", 39, None, [1, 5]),
    (22, 3, "Nattapong", "Kittisak", "nattapong@bib.test", "081-234-5618", 62, None, [5, 1, 2]),
    (23, 3, "Sofia", "Rossi", "sofia@bib.test", "081-234-5619", 35, None, [1, 4, 3]),
    (24, 3, "Win", "Rattanaporn", "win@bib.test", "081-234-5620", 44, None, [3, 4, 1]),
]
STAFF = [2, 3, 4]


def nice_coverage(lo, hi):
    step = 100000 if lo >= 1000000 else (50000 if lo >= 200000 else 10000)
    v = int(round(rnd.uniform(lo, hi) / step) * step)
    return max(lo, min(hi, v))


policies, quotes, fails = [], [], []
pid = qid = 0


def new_quote(user, tier, coverage, risk, off, time, status):
    global qid
    qid += 1
    quotes.append(dict(id=qid, user=user, tier=tier, cov=coverage, risk=risk, off=off, time=time, status=status))
    return qid


def new_policy(user, tier, coverage, risk, buy_off, start_delay=0, method=None, story=None):
    global pid
    pid += 1
    t = TIER[tier]
    buy_time = rtime(9, 21)
    qdelta = rnd.choice([1, 1, 2, 2, 3])          # quotation -> application -> review -> payment
    quote = new_quote(user, tier, coverage, risk, buy_off - qdelta, rtime(9, 19), "Open")
    start = buy_off + start_delay
    m = method or rnd.choices(["Card", "PromptPay", "BankTransfer"], [55, 30, 15])[0]
    last4 = rnd.choice(["4242", "1881", "5100", "7311", "9024", "3456", "8080", "2210"]) if m == "Card" else None
    p = dict(id=pid, user=user, tier=tier, product=t[1], cov=coverage, risk=risk, quote=quote, buy=buy_off,
             buy_time=buy_time, start=start, end=end_off(start, t[8]), method=m, last4=last4,
             remaining=coverage, claims=0, cancelled=False, story=story, qdelta=qdelta)
    policies.append(p)
    return p


# --- story customers -------------------------------------------------------
som_health_prev = new_policy(5, 1, 1000000, 2, -455, 0, "Card", story="som_health_prev")
som_health = new_policy(5, 1, 1000000, 2, -92, 1, "Card", story="som_health")          # renewal
som_ci = new_policy(5, 4, 500000, 2, -330, 0, "BankTransfer", story="som_ci")
som_life = new_policy(5, 7, 1000000, 2, -60, 0, "PromptPay", story="som_life")

fah_health = new_policy(6, 2, 3000000, 1, -120, 0, "Card", story="fah_health")
fah_pa = new_policy(6, 10, 300000, 2, -2, 6, "Card", story="fah_pa")                   # Scheduled, no beneficiaries

# --- everybody else ----------------------------------------------------------
for u in USERS:
    uid, role = u[0], u[1]
    if role != 3 or uid in (5, 6, 7):
        continue
    prefs = u[8]
    n = rnd.choice([3, 4, 4, 5, 5])
    offs = sorted(rnd.sample(range(-450, -8), n))
    for k, off in enumerate(offs):
        prod = prefs[k % len(prefs)] if rnd.random() < 0.85 else rnd.randint(1, 4)
        tier = rnd.choices(TIERS_OF[prod], TIER_WEIGHTS[prod])[0]
        risk = rnd.choices([1, 2, 3, 4], [25, 50, 18, 7])[0]
        new_policy(uid, tier[0], nice_coverage(tier[4], tier[5]), risk, off, rnd.choice([0, 0, 1, 3, 7]))

for uid, tier, cov, off, delay in [(12, 8, 3000000, -3, 10), (19, 10, 200000, -1, 4), (23, 1, 1000000, -4, 12),
                                   (16, 11, 600000, -5, 0), (21, 2, 3000000, -6, 0), (9, 7, 800000, -9, 0)]:
    new_policy(uid, tier, cov, 2, off, delay)

for p in policies:   # keep end dates away from "today" (month-length wobble)
    if -3 <= p["end"] <= 3 and p["story"] is None:
        p["buy"] -= 8
        p["start"] -= 8
        p["end"] = end_off(p["start"], TIER[p["tier"]][8])
        for qq in quotes:
            if qq["id"] == p["quote"]:
                qq["off"] = p["buy"] - p["qdelta"]

for p in rnd.sample([p for p in policies if p["story"] is None and p["buy"] < -60], 4):
    p["cancelled"] = True
    p["cancel_off"] = p["buy"] + rnd.randint(2, 9)


def status_of(p):
    if p["cancelled"]:
        return "Cancelled"
    if p["end"] < 0:
        return "Expired"
    if p["remaining"] <= 0:
        return "Exhausted"
    if p["start"] > 0:
        return "Scheduled"
    return "Active"


# ------------------------------------------------------------ claim catalogue
D = "claim/"
IPD = [
    ("In-patient admission - dengue fever",
     "Admitted for four nights with dengue fever and treated with intravenous fluids and platelet monitoring.",
     [(D + "hospital_invoice.svg", "Itemised hospital invoice"), (D + "discharge_summary.svg", "Discharge summary")]),
    ("In-patient admission - acute appendicitis",
     "Emergency laparoscopic appendectomy followed by a three-night stay.",
     [(D + "hospital_invoice.svg", "Hospital invoice"), (D + "medical_certificate.svg", "Surgeon's medical certificate")]),
    ("In-patient admission - community-acquired pneumonia",
     "Five-night admission for pneumonia confirmed by chest X-ray, treated with intravenous antibiotics.",
     [(D + "xray_chest.svg", "Chest X-ray"), (D + "discharge_summary.svg", "Discharge summary")]),
    ("Day surgery - knee arthroscopy",
     "Arthroscopic repair of a torn meniscus performed as a day-case procedure.",
     [(D + "mri_knee.svg", "Pre-operative MRI"), (D + "hospital_invoice.svg", "Hospital invoice")]),
]
OPD = [
    ("Out-patient treatment - acute gastroenteritis",
     "Out-patient consultation, laboratory tests and medication for acute gastroenteritis.",
     [(D + "prescription.svg", "Prescription"), (D + "lab_report.svg", "Laboratory results")]),
    ("Out-patient treatment - acute bronchitis",
     "Specialist consultation and medication for acute bronchitis.",
     [(D + "prescription.svg", "Prescription"), (D + "hospital_invoice.svg", "Receipt")]),
]
CI = [
    ("Critical illness - early-stage breast cancer",
     "Diagnosed with stage I breast cancer following a biopsy. Pathology report and oncologist's certificate attached.",
     [(D + "pathology_report.svg", "Pathology report"), (D + "medical_certificate.svg", "Oncologist's certificate")]),
    ("Critical illness - acute myocardial infarction",
     "Admitted with chest pain and diagnosed with acute myocardial infarction; treated with coronary angioplasty.",
     [(D + "ecg_report.svg", "ECG report"), (D + "discharge_summary.svg", "Discharge summary")]),
    ("Critical illness - ischaemic stroke",
     "Diagnosed with ischaemic stroke confirmed by MRI; currently in a rehabilitation programme.",
     [(D + "mri_brain.svg", "Brain MRI"), (D + "medical_certificate.svg", "Neurologist's certificate")]),
]
CI_COLORECTAL = ("Critical illness - early-stage colorectal cancer",
                 "Stage I colorectal cancer confirmed by colonoscopy biopsy; surgery completed successfully.",
                 [(D + "pathology_report.svg", "Pathology report"), (D + "discharge_summary.svg", "Discharge summary")])
LIFE = [
    ("Total and permanent disability benefit",
     "Permanent loss of use of both legs following a spinal cord injury, certified by the treating neurologist.",
     [(D + "medical_certificate.svg", "Neurologist's certificate"), (D + "discharge_summary.svg", "Discharge summary")]),
    ("Terminal illness advance benefit",
     "Diagnosed with a terminal illness with a life expectancy of less than 12 months, certified by two specialists.",
     [(D + "medical_certificate.svg", "Specialist certificate"), (D + "pathology_report.svg", "Pathology report")]),
]
PA = [
    ("Accidental injury - fractured wrist",
     "Fell on a staircase at home; distal radius fracture treated with a cast.",
     [(D + "xray_wrist.svg", "Forearm X-ray"), (D + "medical_certificate.svg", "Medical certificate")]),
    ("Road traffic accident - medical expenses",
     "Motorcycle collision on the way to work; treatment for lacerations and a sprained shoulder.",
     [(D + "accident_report.svg", "Police accident report"), (D + "hospital_invoice.svg", "Hospital invoice")]),
    ("Slip and fall - ankle sprain",
     "Slipped on a wet floor at a shopping centre; grade II ankle sprain treated as an out-patient.",
     [(D + "medical_certificate.svg", "Medical certificate"), (D + "prescription.svg", "Prescription")]),
    ("Sports injury - ligament tear",
     "Knee injury during a football match; anterior cruciate ligament tear confirmed by MRI.",
     [(D + "mri_knee.svg", "Knee MRI"), (D + "hospital_invoice.svg", "Hospital invoice")]),
]
APPROVE_NOTES = [
    "Approved in accordance with the policy schedule.",
    "Approved after review of the itemised invoice and medical report.",
    "Approved less the policy deductible.",
    "Approved. Reasonable and customary charges applied.",
    "Approved. Benefit transferred to the registered bank account.",
]
LUMP_NOTE = "Approved in full. Lump-sum benefit paid on confirmed diagnosis."
REJECT_NOTES = {
    "health": ["The condition is pre-existing and excluded under the policy terms.",
               "Treatment was received during the 30-day waiting period.",
               "Expenses are not medically necessary according to the attending physician's report.",
               "Supporting documents are incomplete. Please resubmit with an itemised invoice.",
               "Duplicate of a claim that has already been settled."],
    "opd": ["Out-patient treatment is not covered under the selected plan tier."],
    "ci": ["Diagnosis falls within the 90-day waiting period for critical illness benefits.",
           "The diagnosed condition does not meet the policy definition of a covered critical illness."],
    "pa": ["The injury was not caused by an accident as defined in the policy.",
           "Supporting documents are incomplete. Please resubmit with the police report.",
           "The date of service is before the policy effective date."],
}

claims = []
cid = 0
_rot = {}


def pick(options):
    """Rotate through a template list (shuffled once) instead of random repeats."""
    key = id(options)
    if key not in _rot:
        order = list(range(len(options)))
        rnd.shuffle(order)
        _rot[key] = [order, 0]
    order, i = _rot[key]
    _rot[key][1] = i + 1
    return options[order[i % len(order)]]


def make_claim(p, tpl, amount, sub_off, decision=None, approve=None, note=None, review_hours=None, inc_gap=None):
    global cid
    cid += 1
    gap = inc_gap if inc_gap is not None else rnd.randint(0, 4)
    inc = sub_off - gap
    assert p["start"] <= inc <= p["end"] - 4, (p["id"], inc, p["start"], p["end"])
    assert sub_off <= p["end"] + 24 and sub_off <= -1, (p["id"], sub_off)
    assert not p["cancelled"] and p["remaining"] > 0 and amount <= p["cov"], (p["id"], amount)
    sub_time = rtime(8, 19)
    c = dict(id=cid, policy=p, title=tpl[0], desc=tpl[1], imgs=tpl[2], amount=amount, inc=inc,
             sub=sub_off, sub_time=sub_time, decision=decision)
    if decision:
        hours = review_hours or rnd.randint(6, 96)
        rev_abs = sub_off * 24 + int(sub_time[:2]) + hours
        rev_off, rev_hour = math.floor(rev_abs / 24), rev_abs % 24
        if rev_off > -1:
            rev_off, rev_hour = -1, 18
        if rev_off == sub_off and rev_hour <= int(sub_time[:2]):
            rev_hour = min(int(sub_time[:2]) + 2, 23)
        c["rev"], c["rev_time"] = rev_off, f"{rev_hour:02d}:{rnd.choice(['07', '15', '26', '34', '41', '58'])}"
        c["staff"] = rnd.choice(STAFF) if rnd.random() < 0.9 else 1
        if decision == "Approved":
            ded = TIER[p["tier"]][7]
            max_ok = min(amount - ded, p["remaining"])
            assert max_ok > 0, (p["id"], amount, ded, p["remaining"])
            c["approved"] = min(approve if approve is not None else max_ok, max_ok)
            c["note"] = note or rnd.choice(APPROVE_NOTES)
            p["remaining"] -= c["approved"]
        else:
            c["note"] = note
    p["claims"] += 1
    claims.append(c)
    return c


def round_to(x, step=10):
    return int(x / step) * step


def health_amount(p, opd=False):
    return round_to(rnd.uniform(2400, 9800) if opd else rnd.uniform(24000, 135000), 10)


# ---- story claims
make_claim(som_health_prev, IPD[1], 118400, -300, "Approved", 98400, "Approved less the policy deductible.", 30)
make_claim(som_health, IPD[0], 86500, -40, "Approved", 66500, "Approved less the policy deductible.", 26)
make_claim(som_health, OPD[0], 4200, -18, "Rejected", note=REJECT_NOTES["opd"][0], review_hours=20)
make_claim(som_ci, CI_COLORECTAL, 500000, -95, "Approved", 500000, LUMP_NOTE, 70, inc_gap=12)
make_claim(fah_health, IPD[1], 128400, -1, None, inc_gap=3)


def candidates(product, active_only=False, max_claims=1):
    out = []
    for p in policies:
        if p["product"] != product or p["cancelled"] or p["story"] or p["claims"] >= max_claims or p["remaining"] <= 0:
            continue
        if active_only and not (p["start"] <= -10 and p["end"] >= 8):
            continue
        if not active_only and min(p["end"] - 4, -6) - (p["start"] + 5) < 3:
            continue
        out.append(p)
    rnd.shuffle(out)
    return out


def hist_sub(p):
    lo, hi = p["start"] + 5, min(p["end"] - 4, -6)
    return rnd.randint(lo, hi)


# ---- lump-sum exhaustions: 2 CI + 1 Life TPD
for p in sorted(candidates(2), key=lambda x: x["cov"])[:1]:
    make_claim(p, pick(CI), p["cov"], hist_sub(p), "Approved", p["cov"], LUMP_NOTE, rnd.randint(24, 96))
for p in sorted(candidates(3), key=lambda x: x["cov"])[:1]:
    make_claim(p, LIFE[0], p["cov"], hist_sub(p), "Approved", p["cov"], "Approved in full after independent medical examination.", 90)

# ---- regular approvals: 8 health + 4 PA
for p in candidates(1, max_claims=2)[:8]:
    opd = TIER[p["tier"]][7] == 0 and rnd.random() < 0.3
    tpl = pick(OPD if opd else IPD)
    amount = health_amount(p, opd)
    ded = TIER[p["tier"]][7]
    appr = round_to((amount - ded) * rnd.choice([1, 1, 1, 0.9]), 10)
    make_claim(p, tpl, amount, hist_sub(p), "Approved", appr, "Approved less the policy deductible." if ded else None)
for p in candidates(4)[:3]:
    amount = round_to(rnd.uniform(3500, min(PA_MEDICAL_LIMIT[p["tier"]], 18000)), 10)
    make_claim(p, pick(PA), amount, hist_sub(p), "Approved", amount)

# ---- rejections: 6 health + 3 PA + 2 CI  (Somchai's OPD makes 12)
for p in candidates(1, max_claims=2)[:6]:
    make_claim(p, pick(IPD), health_amount(p), hist_sub(p), "Rejected", note=rnd.choice(REJECT_NOTES["health"]))
for p in candidates(4)[:3]:
    make_claim(p, pick(PA), round_to(rnd.uniform(4000, 30000), 10), hist_sub(p), "Rejected",
               note=rnd.choice(REJECT_NOTES["pa"]))
for p in candidates(2)[:2]:
    make_claim(p, pick(CI), p["cov"], hist_sub(p), "Rejected", note=rnd.choice(REJECT_NOTES["ci"]))

# ---- one claim filed after expiry (inside the 30-day window)
for p in candidates(1, max_claims=2):
    if p["end"] < -40:
        make_claim(p, IPD[2], 64200, p["end"] + 12, "Approved", 64200 - TIER[p["tier"]][7],
                   inc_gap=12 + rnd.randint(4, 6))
        break

# ---- pending queue: 5 health + 3 PA + 1 life (Fah's makes 10)
pending = [(1, 5), (4, 3), (3, 1)]
for prod, n in pending:
    for p in candidates(prod, active_only=True, max_claims=2)[:n]:
        sub = -rnd.randint(1, 3)
        if prod == 1:
            opd = TIER[p["tier"]][7] == 0 and rnd.random() < 0.3
            make_claim(p, pick(OPD if opd else IPD), health_amount(p, opd), sub, inc_gap=rnd.randint(0, 2))
        elif prod == 4:
            make_claim(p, pick(PA), round_to(rnd.uniform(5000, PA_MEDICAL_LIMIT[p["tier"]]), 10), sub,
                       inc_gap=rnd.randint(0, 2))
        else:
            make_claim(p, LIFE[1], p["cov"], sub, inc_gap=rnd.randint(1, 3))


# ------------------------------------------------------- underwriting applications
def to_min(off, hhmm):
    return off * 1440 + int(hhmm[:2]) * 60 + int(hhmm[3:])


def from_min(m):
    off, rest = divmod(m, 1440)
    return off, f"{rest // 60:02d}:{rest % 60:02d}"


# occupation, employer, monthly income, smoker, medical history details, occupation document
PROFILES = {
    5: ("Sales manager", "Siam Trading Co., Ltd.", "50,001-100,000", 0, None, "employment"),
    6: ("Graphic designer", "Freelance", "30,001-50,000", 0, None, "business"),
    8: ("Civil engineer (site supervisor)", "Bangkok Construction PCL", "50,001-100,000", 0, None, "employment"),
    9: ("Accountant", "Chao Phraya Accounting Office", "30,001-50,000", 0, None, "employment"),
    10: ("English teacher", "Riverside International School", "50,001-100,000", 0, None, "employment"),
    11: ("Software developer", "Krungthep Digital Co., Ltd.", "50,001-100,000", 0, None, "employment"),
    12: ("Restaurant owner", "Ban Gun Kitchen", "Above 100,000", 1, None, "business"),
    13: ("Registered nurse", "Rama Medical Center", "30,001-50,000", 0, None, "employment"),
    14: ("Hotel operations manager", "Sukhumvit Grand Hotel", "50,001-100,000", 0, None, "employment"),
    15: ("Government officer", "Ministry of Commerce", "30,001-50,000", 0,
         "Hypertension diagnosed in 2019, controlled with medication.", "employment"),
    16: ("Delivery rider", "Self-employed", "15,000-30,000", 0, None, "business"),
    17: ("Marketing executive", "Lotus Retail Group", "30,001-50,000", 0, None, "employment"),
    18: ("Junior auditor", "Northgate Audit Ltd.", "15,000-30,000", 0, None, "employment"),
    19: ("Fitness trainer", "Pulse Fitness Club", "15,000-30,000", 0, None, "employment"),
    20: ("Pharmacist", "Chulapharm Pharmacy", "50,001-100,000", 0, None, "employment"),
    21: ("Financial analyst", "Andaman Capital Securities", "Above 100,000", 0, None, "employment"),
    22: ("Retired (government pension)", "Retired", "15,000-30,000", 0,
         "Type 2 diabetes since 2016, controlled with oral medication.", "pension"),
    23: ("Architect", "Studio Sathorn Architects", "50,001-100,000", 0, None, "employment"),
    24: ("Factory supervisor", "Eastern Seaboard Components", "30,001-50,000", 1, None, "employment"),
}
APPROVE_APP_NOTES = [None, None, "Identity and occupation verified.", "Documents verified. Standard terms apply.",
                     "Occupation class confirmed by employer certificate."]
REJECT_APP_NOTES = [
    "The occupation stated in the documents does not match the selected occupation class. Please request a new quotation.",
    "The declared medical history requires a full medical examination before cover can be offered.",
    "The proof of occupation is not legible. Please apply again with a clear copy.",
    "The sum insured is too high relative to the declared income.",
]
QUOTE = {qq["id"]: qq for qq in quotes}
apps = []


def make_app(quote_id, submit_min, decision=None, review_min=None, note=None):
    qq = QUOTE[quote_id]
    occ, emp, inc, smoker, medical, kind = PROFILES[qq["user"]]
    product = TIER[qq["tier"]][1]
    docs = [("Identity", "application/id_card_copy.svg", "Copy of ID card")]
    if kind == "business":
        docs.append(("Occupation", "application/business_registration.svg", "Business registration"))
    elif kind == "pension":
        docs.append(("Occupation", "application/salary_slip.svg", "Pension statement"))
    else:
        docs.append(("Occupation", "application/employment_certificate.svg", "Employment certificate"))
    if medical or (product in (1, 2, 3) and qq["cov"] >= 3000000):
        docs.append(("Medical", "application/health_checkup.svg", "Health check-up report"))
    elif product in (3, 5):
        docs.append(("Income", "application/salary_slip.svg", "Salary slip"))
    app = dict(id=len(apps) + 1, quote=quote_id, occ=occ, emp=emp, inc=inc, smoker=smoker, medical=medical,
               docs=docs, submit=submit_min, decision=decision, review=review_min, note=note,
               staff=rnd.choice(STAFF))
    apps.append(app)
    return app


for p in policies:
    q_min = to_min(QUOTE[p["quote"]]["off"], QUOTE[p["quote"]]["time"])
    buy_min = to_min(p["buy"], p["buy_time"])
    sub = q_min + rnd.randint(20, 90)
    rev = min(sub + rnd.randint(2, 22) * 60 + rnd.randint(0, 50), buy_min - 60)
    assert rev > sub + 20, (p["id"], q_min, sub, rev, buy_min)
    make_app(p["quote"], sub, "Approved", rev, rnd.choice(APPROVE_APP_NOTES))

# ------------------------------------------------------------- failed checkouts
for p in rnd.sample([p for p in policies if p["method"] == "Card"], 9):
    fails.append(dict(quote=p["quote"], off=p["buy"], time=p["buy_time"], result="DECLINED", last4="0002",
                      method="Card", before=True))
cust_ids = [u[0] for u in USERS if u[1] == 3 and u[0] != 7]
extra_open, extra_expired = [], []
# open quotations: 3 approved (one declined card each, awaiting payment), 5 awaiting review, 1 without application
open_users = rnd.sample([u for u in cust_ids if u not in (5, 6)], 9)
for i, off in enumerate([-5, -4, -3, -3, -2, -2, -1, -1, -1]):
    tier = rnd.choice(TIERS_OF[rnd.randint(1, 5)])
    extra_open.append(new_quote(open_users[i], tier[0], nice_coverage(tier[4], tier[5]), rnd.randint(1, 3),
                                off, rtime(9, 16), "Open"))
QUOTE.update({qq["id"]: qq for qq in quotes})
for i, qq_id in enumerate(extra_open):
    q_min = to_min(QUOTE[qq_id]["off"], QUOTE[qq_id]["time"])
    sub = q_min + rnd.randint(60, 180)
    if i < 3:
        rev = sub + rnd.randint(3, 18) * 60
        make_app(qq_id, sub, "Approved", rev, rnd.choice(APPROVE_APP_NOTES))
        f_off, f_time = from_min(rev + 120)
        fails.append(dict(quote=qq_id, off=f_off, time=f_time, result="DECLINED", last4="0002",
                          method="Card", before=False))
    elif i < 8:
        make_app(qq_id, sub)
# old quotations: 3 approved but never paid (expired), 4 declined by underwriting, the rest expired untouched
for i in range(18):
    tier = rnd.choice(TIERS_OF[rnd.randint(1, 5)])
    extra_expired.append(new_quote(rnd.choice(cust_ids), tier[0], nice_coverage(tier[4], tier[5]),
                                   rnd.randint(1, 3), -rnd.randint(20, 400), rtime(9, 17), "Expired"))
QUOTE.update({qq["id"]: qq for qq in quotes})
for i, qq_id in enumerate(extra_expired[:7]):
    QUOTE[qq_id]["status"] = "Open"
    q_min = to_min(QUOTE[qq_id]["off"], QUOTE[qq_id]["time"])
    sub = q_min + rnd.randint(30, 240)
    rev = sub + rnd.randint(4, 26) * 60
    if i < 3:
        make_app(qq_id, sub, "Approved", rev, rnd.choice(APPROVE_APP_NOTES))
        fails.append(dict(quote=qq_id, off=QUOTE[qq_id]["off"] + 9, time="10:15", result="ERROR", last4=None,
                          method="PromptPay", before=False))
    else:
        make_app(qq_id, sub, "Rejected", rev, REJECT_APP_NOTES[i - 3])

first_activity = {}
for qq in quotes:
    first_activity[qq["user"]] = min(first_activity.get(qq["user"], 0), qq["off"])

# ------------------------------------------------ chronological renumbering
_qmap = {}
for new_id, qq in enumerate(sorted(quotes, key=lambda x: (x["off"], x["time"], x["id"])), start=1):
    _qmap[qq["id"]] = new_id
for qq in quotes:
    qq["id"] = _qmap[qq["id"]]
quotes.sort(key=lambda x: x["id"])
for p in policies:
    p["quote"] = _qmap[p["quote"]]
for f in fails:
    f["quote"] = _qmap[f["quote"]]
for new_id, p in enumerate(sorted(policies, key=lambda x: (x["buy"], x["buy_time"], x["id"])), start=1):
    p["id"] = new_id
for new_id, c in enumerate(sorted(claims, key=lambda x: (x["sub"], x["sub_time"], x["id"])), start=1):
    c["id"] = new_id
for ap in apps:
    ap["quote"] = _qmap[ap["quote"]]
for new_id, ap in enumerate(sorted(apps, key=lambda x: (x["submit"], x["id"])), start=1):
    ap["id"] = new_id

# ------------------------------------------------------------- beneficiaries
REL = ["Spouse", "Mother", "Father", "Daughter", "Son", "Sister", "Brother"]
FIRST = ["Somsri", "Prasit", "Anong", "Wichai", "Kanya", "Narong", "Malee", "Sakda", "Ratana", "Boonmee",
         "Lamai", "Chaiwat", "Pornthip", "Anan", "Siriwan", "Thanakorn", "Napat", "Kritsada"]
SPLITS = [[100], [50, 50], [60, 40], [70, 30], [50, 25, 25], [40, 30, 20, 10], [34, 33, 33], [25, 25, 25, 25]]
benefs = []
for p in policies:
    required = PRODUCTS[p["product"] - 1][7] == 1
    optional = p["product"] in (5,) and rnd.random() < 0.5
    if (required and p["story"] != "fah_pa") or optional:
        split = rnd.choice(SPLITS[:4] if optional else SPLITS)
        last = USERS[p["user"] - 1][3]
        for n, r, pct in zip(rnd.sample(FIRST, len(split)), rnd.sample(REL, len(split)), split):
            benefs.append((p["id"], f"{n} {last}", r, pct))

# ======================================================================= WRITE
L = []
a = L.append
a("""-- =====================================================================
--  BIB Assurance (Bangkok Insurance & Benefits)
--  "Trusted Protection for Every Stage of Life"
--  Script 3 of 3 : 03_seed_data.sql
--  Sample data for EVERY table.  Run AFTER 01_schema.sql and 02_routines.sql.
--  * All dates are relative to CURDATE(), so the data always looks current.
--  * Claims and assessments go through the real triggers: validation,
--    benefit deduction and audit rows are produced by the database.
--  * Password for EVERY sample account: Bib@2026 (stored as a Django hash).
--  (generated by database/tools/make_seed.py - edit that file, not this one)
-- =====================================================================

USE bibdb;
SET @OLD_SAFE_UPDATES = @@SQL_SAFE_UPDATES;
SET SQL_SAFE_UPDATES = 0;   -- MySQL Workbench safe-update mode off for this script

-- ---------------------------------------------------------------------
-- Seed-only helper procedures (dropped again at the end of the script)
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS seed_quote;
DELIMITER $$
CREATE PROCEDURE seed_quote(
  IN p_quote_id INT, IN p_user_id INT, IN p_tier_id INT,
  IN p_coverage DECIMAL(12,2), IN p_risk INT,
  IN p_created DATETIME, IN p_status VARCHAR(20)
)
BEGIN
  DECLARE v_age INT;
  DECLARE v_product INT;
  SET v_age = fn_age((SELECT date_of_birth FROM app_user WHERE user_id = p_user_id), DATE(p_created));
  SET v_product = (SELECT product_id FROM coverage_tier WHERE tier_id = p_tier_id);
  INSERT INTO premium_quote (quote_id, user_id, tier_id, coverage_amount, insured_age, risk_level,
                             age_multiplier, risk_multiplier, quoted_premium, quote_status,
                             created_at, expires_at)
  VALUES (p_quote_id, p_user_id, p_tier_id, p_coverage, v_age, p_risk,
          fn_get_multiplier(v_product, 'AGE', v_age), fn_get_multiplier(v_product, 'RISK', p_risk),
          fn_calc_premium(p_tier_id, v_age, p_risk, p_coverage), p_status,
          p_created, DATE_ADD(p_created, INTERVAL 7 DAY));
END $$
DELIMITER ;

DROP PROCEDURE IF EXISTS seed_policy;
DELIMITER $$
CREATE PROCEDURE seed_policy(
  IN p_policy_id INT, IN p_quote_id INT, IN p_start DATE,
  IN p_purchased DATETIME, IN p_method VARCHAR(20), IN p_last4 CHAR(4)
)
BEGIN
  DECLARE v_user INT;
  DECLARE v_tier INT;
  DECLARE v_cov DECIMAL(12,2);
  DECLARE v_prem DECIMAL(10,2);
  DECLARE v_months INT;
  DECLARE v_number VARCHAR(20);
  DECLARE v_txn VARCHAR(40);
  SELECT q.user_id, q.tier_id, q.coverage_amount, q.quoted_premium, t.duration_months
    INTO v_user, v_tier, v_cov, v_prem, v_months
    FROM premium_quote q INNER JOIN coverage_tier t ON q.tier_id = t.tier_id
    WHERE q.quote_id = p_quote_id;
  SET v_number = fn_format_number('BIB', p_policy_id, DATE(p_purchased));
  INSERT INTO policy (policy_id, policy_number, user_id, tier_id, quote_id, coverage_amount,
                      remaining_coverage, premium_amount, start_date, end_date, policy_status, created_at)
  VALUES (p_policy_id, v_number, v_user, v_tier, p_quote_id, v_cov, v_cov, v_prem, p_start,
          DATE_SUB(DATE_ADD(p_start, INTERVAL v_months MONTH), INTERVAL 1 DAY), 'Active', p_purchased);
  SET v_txn = CONCAT('TXN-', DATE_FORMAT(p_purchased, '%Y%m%d%H%i%s'), '-', LPAD(p_policy_id, 6, '0'));
  INSERT INTO payment (policy_id, user_id, amount, payment_method, card_last4, payment_status, transaction_ref, paid_at)
  VALUES (p_policy_id, v_user, v_prem, p_method, IF(p_method = 'Card', p_last4, NULL), 'Paid', v_txn, p_purchased);
  INSERT INTO checkout_log (user_id, quote_id, policy_id, amount, payment_method, card_last4, result, message, attempted_at)
  VALUES (v_user, p_quote_id, p_policy_id, v_prem, p_method, IF(p_method = 'Card', p_last4, NULL), 'SUCCESS',
          CONCAT('Policy ', v_number, ' issued. Payment ', v_txn, '.'), p_purchased);
  UPDATE premium_quote SET quote_status = 'Converted' WHERE quote_id = p_quote_id;
END $$
DELIMITER ;

DROP PROCEDURE IF EXISTS seed_failed_checkout;
DELIMITER $$
CREATE PROCEDURE seed_failed_checkout(
  IN p_quote_id INT, IN p_attempted DATETIME, IN p_result VARCHAR(20),
  IN p_method VARCHAR(20), IN p_last4 CHAR(4)
)
BEGIN
  INSERT INTO checkout_log (user_id, quote_id, policy_id, amount, payment_method, card_last4, result, message, attempted_at)
  SELECT q.user_id, q.quote_id, NULL, q.quoted_premium, p_method, p_last4, p_result,
         IF(p_result = 'DECLINED',
            'Payment declined by the card issuer. Policy was not issued.',
            'Quotation expired before payment.'),
         p_attempted
  FROM premium_quote q WHERE q.quote_id = p_quote_id;
  IF p_result = 'ERROR' THEN
    UPDATE premium_quote SET quote_status = 'Expired' WHERE quote_id = p_quote_id;
  END IF;
END $$
DELIMITER ;

DROP PROCEDURE IF EXISTS seed_application;
DELIMITER $$
CREATE PROCEDURE seed_application(
  IN p_application_id INT, IN p_quote_id INT,
  IN p_occupation VARCHAR(100), IN p_employer VARCHAR(120), IN p_income VARCHAR(30),
  IN p_smoker TINYINT, IN p_medical TINYINT, IN p_details VARCHAR(500),
  IN p_submitted DATETIME,
  IN p_type1 VARCHAR(20), IN p_path1 VARCHAR(255), IN p_cap1 VARCHAR(160),
  IN p_type2 VARCHAR(20), IN p_path2 VARCHAR(255), IN p_cap2 VARCHAR(160),
  IN p_type3 VARCHAR(20), IN p_path3 VARCHAR(255), IN p_cap3 VARCHAR(160)
)
BEGIN
  -- same INSERTs as sp_submit_application (trg_application_before_insert validates)
  INSERT INTO underwriting_application (application_id, application_number, quote_id, user_id, occupation, employer,
                                        monthly_income, is_smoker, has_medical_history, health_details, submitted_at)
  SELECT p_application_id, fn_format_number('APP', p_application_id, DATE(p_submitted)), q.quote_id, q.user_id,
         p_occupation, p_employer, p_income, p_smoker, p_medical, p_details, p_submitted
  FROM premium_quote q WHERE q.quote_id = p_quote_id;
  INSERT INTO application_document (application_id, document_type, image_path, caption, uploaded_at)
  VALUES (p_application_id, p_type1, p_path1, p_cap1, p_submitted);
  INSERT INTO application_document (application_id, document_type, image_path, caption, uploaded_at)
  VALUES (p_application_id, p_type2, p_path2, p_cap2, p_submitted);
  IF p_path3 IS NOT NULL THEN
    INSERT INTO application_document (application_id, document_type, image_path, caption, uploaded_at)
    VALUES (p_application_id, p_type3, p_path3, p_cap3, p_submitted);
  END IF;
END $$
DELIMITER ;

DROP PROCEDURE IF EXISTS seed_application_review;
DELIMITER $$
CREATE PROCEDURE seed_application_review(
  IN p_application_id INT, IN p_staff_id INT, IN p_decision VARCHAR(20),
  IN p_note VARCHAR(255), IN p_reviewed DATETIME
)
BEGIN
  -- same UPDATE as sp_review_application: trg_application_before_update checks
  -- the rules, trg_application_after_update opens the payment window / declines the quote
  UPDATE underwriting_application
    SET app_status = p_decision, reviewed_by = p_staff_id, review_note = p_note, reviewed_at = p_reviewed
    WHERE application_id = p_application_id;
END $$
DELIMITER ;

DROP PROCEDURE IF EXISTS seed_claim;
DELIMITER $$
CREATE PROCEDURE seed_claim(
  IN p_claim_id INT, IN p_policy_id INT, IN p_incident DATE,
  IN p_title VARCHAR(120), IN p_description TEXT, IN p_amount DECIMAL(12,2),
  IN p_submitted DATETIME,
  IN p_img1 VARCHAR(255), IN p_cap1 VARCHAR(160),
  IN p_img2 VARCHAR(255), IN p_cap2 VARCHAR(160)
)
BEGIN
  INSERT INTO claim (claim_id, claim_number, policy_id, incident_date, incident_title,
                     incident_description, claimed_amount, submitted_at)
  VALUES (p_claim_id, fn_format_number('CLM', p_claim_id, DATE(p_submitted)), p_policy_id, p_incident,
          p_title, p_description, p_amount, p_submitted);
  INSERT INTO claim_evidence (claim_id, image_path, caption, uploaded_at)
  VALUES (p_claim_id, p_img1, p_cap1, p_submitted);
  IF p_img2 IS NOT NULL THEN
    INSERT INTO claim_evidence (claim_id, image_path, caption, uploaded_at)
    VALUES (p_claim_id, p_img2, p_cap2, p_submitted);
  END IF;
END $$
DELIMITER ;

DROP PROCEDURE IF EXISTS seed_review;
DELIMITER $$
CREATE PROCEDURE seed_review(
  IN p_claim_id INT, IN p_staff_id INT, IN p_decision VARCHAR(20),
  IN p_amount DECIMAL(12,2), IN p_note VARCHAR(255), IN p_reviewed DATETIME
)
BEGIN
  -- same UPDATE as sp_review_claim: trg_claim_before_update validates,
  -- trg_claim_after_update deducts the benefit, the audit trigger logs it
  UPDATE claim
    SET claim_status = p_decision,
        approved_amount = IF(p_decision = 'Approved', p_amount, NULL),
        reviewed_by = p_staff_id,
        review_note = p_note,
        reviewed_at = p_reviewed
    WHERE claim_id = p_claim_id;
END $$
DELIMITER ;
""")
a("-- 1) role")
a("INSERT INTO role (role_id, role_code, role_name) VALUES\n  (1, 'ADMIN', 'Administrator'),\n"
  "  (2, 'STAFF', 'Claims Officer'),\n  (3, 'CUSTOMER', 'Customer');\n")
a("-- 2) app_user  (password for every account: Bib@2026)")
rows = []
for u in USERS:
    uid, role, fn, ln, email, phone, age, avatar, _ = u
    join = -470 - uid * 3 if uid <= 4 else min(first_activity.get(uid, 0), 0) - rnd.randint(2, 25)
    created = "NOW()" if uid == 7 else dt(join, rtime(9, 18))
    last_login = "NULL" if uid == 7 else dt(-rnd.randint(1, 9), rtime(8, 21))
    rows.append(f"  ({uid}, {role}, {q(email)}, {q(make_password(DEMO_PASSWORD))}, {q(fn)}, {q(ln)}, {q(phone)}, "
                f"DATE_SUB(DATE_SUB(CURDATE(), INTERVAL {age} YEAR), INTERVAL {rnd.randint(10, 340)} DAY), "
                f"{q(avatar) if avatar else 'NULL'}, 1, {created}, {last_login})")
a("INSERT INTO app_user (user_id, role_id, email, password_hash, first_name, last_name, phone,\n"
  "                      date_of_birth, avatar_path, is_active, created_at, last_login_at) VALUES")
a(",\n".join(rows) + ";\n")
a("-- 3) product")
a("INSERT INTO product (product_id, product_code, product_name, tagline, description, category,\n"
  "                     thumbnail_path, requires_beneficiary, is_active, created_at) VALUES")
a(",\n".join(f"  ({p[0]}, {q(p[1])}, {q(p[2])}, {q(p[3])}, {q(p[4])}, {q(p[5])}, {q(p[6])}, {p[7]}, 1, {dt(-500, '10:00')})"
             for p in PRODUCTS) + ";\n")
a("-- 4) coverage_tier  (base_annual_premium = 12-month premium at min_coverage, Standard class, age 25-39)")
a("INSERT INTO coverage_tier (tier_id, product_id, tier_name, tier_level, min_coverage, max_coverage,\n"
  "                           base_annual_premium, deductible, duration_months, perks) VALUES")
a(",\n".join(f"  ({t[0]}, {t[1]}, {q(t[2])}, {t[3]}, {t[4]:.2f}, {t[5]:.2f}, {t[6]:.2f}, {t[7]:.2f}, {t[8]}, {q(t[9])})"
             for t in TIERS) + ";\n")
a("-- 5) premium_factor  (NULL product_id = applies to every plan)")
a("INSERT INTO premium_factor (factor_id, product_id, factor_type, range_min, range_max, multiplier, label) VALUES")
a(",\n".join(f"  ({f[0]}, {'NULL' if f[1] is None else f[1]}, {q(f[2])}, {f[3]}, {f[4]}, {f[5]}, {q(f[6])})"
             for f in FACTORS) + ";\n")
a("-- 6) premium_quote  (premium calculated by fn_calc_premium)")
for qq in quotes:
    a(f"CALL seed_quote({qq['id']}, {qq['user']}, {qq['tier']}, {qq['cov']:.2f}, {qq['risk']}, "
      f"{dt(qq['off'], qq['time'])}, {q(qq['status'])});")
a("\n-- 14) underwriting_application + 15) application_document (submitted -> assessed by an officer)")
a("-- 7) policy + 8) payment + 9) checkout_log  (a policy can only be bought after approval)")
a("--    Everything below is chronological: application, decision, payment.")
events = [(p["buy"], p["buy_time"], "policy", p) for p in policies]
for ap in apps:
    events.append((*from_min(ap["submit"]), "app", ap))
    if ap["decision"]:
        events.append((*from_min(ap["review"]), "review", ap))
for f in fails:
    t = f["time"]
    if f["before"]:
        t = f"{t[:2]}:{max(int(t[3:]) - 3, 0):02d}"
    events.append((f["off"], t, "fail", f))
ORDER = {"app": 0, "review": 1, "fail": 2, "policy": 3}
for off, t, kind, obj in sorted(events, key=lambda e: (e[0], e[1], ORDER[e[2]])):
    if kind == "policy":
        p = obj
        a(f"CALL seed_policy({p['id']}, {p['quote']}, {dd(p['start'])}, {dt(p['buy'], p['buy_time'])}, "
          f"{q(p['method'])}, {q(p['last4']) if p['last4'] else 'NULL'});")
    elif kind == "app":
        ap = obj
        d3 = ap["docs"][2] if len(ap["docs"]) > 2 else (None, None, None)
        docs = ", ".join(", ".join(q(x) if x else "NULL" for x in d) for d in (ap["docs"][0], ap["docs"][1], d3))
        a(f"CALL seed_application({ap['id']}, {ap['quote']}, {q(ap['occ'])}, {q(ap['emp'])}, {q(ap['inc'])}, "
          f"{ap['smoker']}, {1 if ap['medical'] else 0}, {q(ap['medical']) if ap['medical'] else 'NULL'}, "
          f"{dt(off, t)}, {docs});")
    elif kind == "review":
        ap = obj
        a(f"CALL seed_application_review({ap['id']}, {ap['staff']}, {q(ap['decision'])}, "
          f"{q(ap['note']) if ap['note'] else 'NULL'}, {dt(off, t)});")
    else:
        a(f"CALL seed_failed_checkout({obj['quote']}, {dt(off, t)}, {q(obj['result'])}, {q(obj['method'])}, "
          f"{q(obj['last4']) if obj['last4'] else 'NULL'});")
a("\n-- cancellations inside the 14-day free-look period (policy + refund)")
for p in policies:
    if p["cancelled"]:
        a(f"UPDATE policy SET policy_status = 'Cancelled', cancelled_at = {dt(p['cancel_off'], '11:20')} WHERE policy_id = {p['id']};")
        a(f"UPDATE payment SET payment_status = 'Refunded', refunded_at = {dt(p['cancel_off'], '11:20')} WHERE policy_id = {p['id']};")
a("""
-- 10) policy_beneficiary  (every Life Protector and PA Shield policy = exactly 100%)
--     Fah's new PA Shield policy (starting in a few days) has no beneficiaries
--     yet on purpose, so the "Action required" reminder can be demonstrated.""")
a("INSERT INTO policy_beneficiary (policy_id, full_name, relationship, allocation_pct) VALUES")
a(",\n".join(f"  ({b[0]}, {q(b[1])}, {q(b[2])}, {b[3]:.2f})" for b in benefs) + ";\n")
a("-- 11) claim + 12) claim_evidence + 13) claim_status_audit (written by triggers)")
a("--     Chronological: submissions and assessments interleaved by date.")
cev = []
for c in claims:
    cev.append((c["sub"], c["sub_time"], 0, "submit", c))
    if c["decision"]:
        cev.append((c["rev"], c["rev_time"], 1, "review", c))
for off, t, _, kind, c in sorted(cev, key=lambda e: (e[0], e[1], e[2])):
    if kind == "submit":
        imgs = c["imgs"] + [(None, None)] * (2 - len(c["imgs"]))
        a(f"CALL seed_claim({c['id']}, {c['policy']['id']}, {dd(c['inc'])}, {q(c['title'])},\n"
          f"  {q(c['desc'])},\n  {c['amount']:.2f}, {dt(c['sub'], c['sub_time'])}, {q(imgs[0][0])}, {q(imgs[0][1])}, "
          f"{q(imgs[1][0]) if imgs[1][0] else 'NULL'}, {q(imgs[1][1]) if imgs[1][1] else 'NULL'});")
    else:
        amt = f"{c['approved']:.2f}" if c["decision"] == "Approved" else "NULL"
        a(f"CALL seed_review({c['id']}, {c['staff']}, {q(c['decision'])}, {amt}, {q(c['note'])}, {dt(c['rev'], c['rev_time'])});")
a("""
-- Clean up the seed helpers and bring every status up to date
DROP PROCEDURE IF EXISTS seed_quote;
DROP PROCEDURE IF EXISTS seed_policy;
DROP PROCEDURE IF EXISTS seed_failed_checkout;
DROP PROCEDURE IF EXISTS seed_claim;
DROP PROCEDURE IF EXISTS seed_review;
DROP PROCEDURE IF EXISTS seed_application;
DROP PROCEDURE IF EXISTS seed_application_review;
CALL sp_refresh_policy_status();
SET SQL_SAFE_UPDATES = @OLD_SAFE_UPDATES;

-- Row counts for every table (should all be > 0)
SELECT 'role' AS table_name, COUNT(*) AS row_count FROM role
UNION ALL SELECT 'app_user', COUNT(*) FROM app_user
UNION ALL SELECT 'product', COUNT(*) FROM product
UNION ALL SELECT 'coverage_tier', COUNT(*) FROM coverage_tier
UNION ALL SELECT 'premium_factor', COUNT(*) FROM premium_factor
UNION ALL SELECT 'premium_quote', COUNT(*) FROM premium_quote
UNION ALL SELECT 'policy', COUNT(*) FROM policy
UNION ALL SELECT 'payment', COUNT(*) FROM payment
UNION ALL SELECT 'checkout_log', COUNT(*) FROM checkout_log
UNION ALL SELECT 'policy_beneficiary', COUNT(*) FROM policy_beneficiary
UNION ALL SELECT 'claim', COUNT(*) FROM claim
UNION ALL SELECT 'claim_evidence', COUNT(*) FROM claim_evidence
UNION ALL SELECT 'claim_status_audit', COUNT(*) FROM claim_status_audit
UNION ALL SELECT 'underwriting_application', COUNT(*) FROM underwriting_application
UNION ALL SELECT 'application_document', COUNT(*) FROM application_document;""")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(L) + "\n")

st, cs, byprod = {}, {}, {}
for p in policies:
    st[status_of(p)] = st.get(status_of(p), 0) + 1
    byprod[p["product"]] = byprod.get(p["product"], 0) + 1
for c in claims:
    k = c["decision"] or "Pending"
    cs[k] = cs.get(k, 0) + 1
print("policies", len(policies), st, "by product", byprod)
print("applications", len(apps), {k: sum(1 for x in apps if (x["decision"] or "Pending") == k) for k in ("Pending", "Approved", "Rejected")})
print("quotes", len(quotes), "fails", len(fails), "claims", len(claims), cs, "beneficiaries", len(benefs))
