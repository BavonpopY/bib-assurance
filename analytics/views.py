"""
Module 6 : Admin Analytics Dashboard
  Complex reporting SQL from Labs 6-7 / Homework 1-2:
  multi-table JOINs, GROUP BY, WITH ROLLUP, HAVING, CASE, scalar /
  correlated subqueries, NOT EXISTS, derived tables - plus the views
  vw_product_sales, vw_monthly_premium, vw_claim_ratio and the
  procedure sp_dashboard_kpis.
  The SQL lives in the two dictionaries below (and in README.md); it is
  never rendered on the web pages.
"""
from datetime import date

from django.shortcuts import render

from projectweb.dbhelper import call_proc, call_proc_one, query_all
from projectweb.sessionhelper import role_required

SQL = {
    'kpis': "CALL sp_dashboard_kpis();",
    'monthly_premium': "SELECT period, net_premium, payments\nFROM vw_monthly_premium\nORDER BY period;",
    'monthly_payout': (
        "SELECT DATE_FORMAT(reviewed_at, '%Y-%m') AS period,\n"
        "       SUM(approved_amount) AS payout, COUNT(*) AS claims_paid\n"
        "FROM claim\n"
        "WHERE claim_status = 'Approved'\n"
        "GROUP BY DATE_FORMAT(reviewed_at, '%Y-%m');"),
    'best_sellers': (
        "SELECT product_name,\n"
        "       SUM(policies_sold) AS sold,\n"
        "       SUM(premium_written) AS premium,\n"
        "       SUM(unique_customers) AS customers\n"
        "FROM vw_product_sales\n"
        "GROUP BY product_id, product_name\n"
        "ORDER BY sold DESC;"),
    'claim_status': (
        "SELECT claim_status, COUNT(*) AS n,\n"
        "       SUM(claimed_amount) AS claimed,\n"
        "       IFNULL(SUM(approved_amount), 0) AS paid\n"
        "FROM claim\n"
        "GROUP BY claim_status\n"
        "ORDER BY FIELD(claim_status, 'Approved', 'Pending', 'Rejected');"),
    'loss_ratio': "SELECT *\nFROM vw_claim_ratio\nORDER BY loss_ratio_pct DESC;",
    'age_bands': (
        "SELECT CASE\n"
        "         WHEN fn_age(u.date_of_birth, CURDATE()) BETWEEN 18 AND 24 THEN '18-24'\n"
        "         WHEN fn_age(u.date_of_birth, CURDATE()) BETWEEN 25 AND 39 THEN '25-39'\n"
        "         WHEN fn_age(u.date_of_birth, CURDATE()) BETWEEN 40 AND 59 THEN '40-59'\n"
        "         ELSE '60+'\n"
        "       END AS age_band,\n"
        "       COUNT(DISTINCT u.user_id) AS customers,\n"
        "       COUNT(po.policy_id) AS policies\n"
        "FROM app_user AS u\n"
        "INNER JOIN role AS r ON u.role_id = r.role_id\n"
        "LEFT OUTER JOIN policy AS po ON po.user_id = u.user_id AND po.policy_status <> 'Cancelled'\n"
        "WHERE r.role_code = 'CUSTOMER'\n"
        "GROUP BY age_band\n"
        "ORDER BY age_band;"),
    'checkout': (
        "SELECT result, COUNT(*) AS n, IFNULL(SUM(amount), 0) AS amount\n"
        "FROM checkout_log\n"
        "GROUP BY result;"),
    'top_customers': (
        "SELECT u.user_id, CONCAT(u.first_name, ' ', u.last_name) AS customer_name,\n"
        "       u.avatar_path,\n"
        "       COUNT(DISTINCT po.policy_id) AS policies,\n"
        "       SUM(pay.amount) AS total_paid\n"
        "FROM app_user AS u\n"
        "INNER JOIN policy AS po ON po.user_id = u.user_id\n"
        "INNER JOIN payment AS pay ON pay.policy_id = po.policy_id AND pay.payment_status = 'Paid'\n"
        "GROUP BY u.user_id, customer_name, u.avatar_path\n"
        "HAVING COUNT(DISTINCT po.policy_id) >= 3\n"
        "ORDER BY total_paid DESC\n"
        "LIMIT 5;"),
    'staff': (
        "SELECT CONCAT(s.first_name, ' ', s.last_name) AS reviewer, s.avatar_path,\n"
        "       COUNT(*) AS reviewed,\n"
        "       SUM(c.claim_status = 'Approved') AS approved,\n"
        "       SUM(c.claim_status = 'Rejected') AS rejected,\n"
        "       ROUND(AVG(TIMESTAMPDIFF(HOUR, c.submitted_at, c.reviewed_at)), 1) AS avg_hours,\n"
        "       IFNULL(SUM(c.approved_amount), 0) AS paid_out\n"
        "FROM claim AS c\n"
        "INNER JOIN app_user AS s ON c.reviewed_by = s.user_id\n"
        "GROUP BY s.user_id, reviewer, s.avatar_path\n"
        "ORDER BY reviewed DESC;"),
    'above_avg': (
        "SELECT product_name, loss_ratio_pct, total_payout, net_premium\n"
        "FROM vw_claim_ratio\n"
        "WHERE loss_ratio_pct > (SELECT AVG(loss_ratio_pct) FROM vw_claim_ratio)\n"
        "ORDER BY loss_ratio_pct DESC;"),
}

REPORT_SQL = {
    'sales_rollup': (
        "SELECT IFNULL(p.product_name, 'All products') AS product_name,\n"
        "       IFNULL(t.tier_name, IF(p.product_name IS NULL, '', 'Subtotal')) AS tier_name,\n"
        "       COUNT(po.policy_id) AS policies,\n"
        "       SUM(po.premium_amount) AS premium,\n"
        "       SUM(po.coverage_amount) AS coverage\n"
        "FROM policy AS po\n"
        "INNER JOIN coverage_tier AS t ON po.tier_id = t.tier_id\n"
        "INNER JOIN product AS p ON t.product_id = p.product_id\n"
        "WHERE po.policy_status <> 'Cancelled'\n"
        "GROUP BY p.product_name, t.tier_name WITH ROLLUP;"),
    'monthly_rollup': (
        "SELECT IFNULL(period, 'Grand total') AS period,\n"
        "       COUNT(*) AS payments,\n"
        "       SUM(amount) AS gross,\n"
        "       SUM(IF(payment_status = 'Refunded', amount, 0)) AS refunded,\n"
        "       SUM(IF(payment_status = 'Paid', amount, 0)) AS net\n"
        "FROM (SELECT DATE_FORMAT(paid_at, '%Y-%m') AS period, amount, payment_status\n"
        "      FROM payment\n"
        "      WHERE paid_at >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)) AS last_year\n"
        "GROUP BY period WITH ROLLUP;"),
    'claims_rollup': (
        "SELECT IFNULL(p.product_name, 'All products') AS product_name,\n"
        "       IFNULL(c.claim_status, IF(p.product_name IS NULL, '', 'Subtotal')) AS claim_status,\n"
        "       COUNT(*) AS claims,\n"
        "       SUM(c.claimed_amount) AS claimed,\n"
        "       IFNULL(SUM(c.approved_amount), 0) AS paid\n"
        "FROM claim AS c\n"
        "INNER JOIN policy AS po ON c.policy_id = po.policy_id\n"
        "INNER JOIN coverage_tier AS t ON po.tier_id = t.tier_id\n"
        "INNER JOIN product AS p ON t.product_id = p.product_id\n"
        "GROUP BY p.product_name, c.claim_status WITH ROLLUP;"),
    'renewals': (
        "SELECT policy_number, customer_name, customer_email, product_name, tier_name,\n"
        "       end_date, days_remaining, remaining_coverage\n"
        "FROM vw_policy_overview\n"
        "WHERE live_status = 'Active' AND days_remaining <= 30\n"
        "ORDER BY days_remaining;"),
    'never_claimed': (
        "SELECT u.user_id, CONCAT(u.first_name, ' ', u.last_name) AS customer_name, u.email,\n"
        "       (SELECT COUNT(*) FROM policy p WHERE p.user_id = u.user_id) AS policies\n"
        "FROM app_user AS u\n"
        "INNER JOIN role AS r ON u.role_id = r.role_id\n"
        "WHERE r.role_code = 'CUSTOMER'\n"
        "  AND EXISTS (SELECT 1 FROM policy p WHERE p.user_id = u.user_id)\n"
        "  AND NOT EXISTS (SELECT 1 FROM claim c\n"
        "                  INNER JOIN policy p ON c.policy_id = p.policy_id\n"
        "                  WHERE p.user_id = u.user_id)\n"
        "ORDER BY policies DESC, customer_name;"),
    'above_product_avg': (
        "SELECT po.policy_number, p.product_name, po.premium_amount,\n"
        "       (SELECT ROUND(AVG(po2.premium_amount), 2)\n"
        "          FROM policy po2\n"
        "          INNER JOIN coverage_tier t2 ON po2.tier_id = t2.tier_id\n"
        "          WHERE t2.product_id = t.product_id) AS product_avg\n"
        "FROM policy AS po\n"
        "INNER JOIN coverage_tier AS t ON po.tier_id = t.tier_id\n"
        "INNER JOIN product AS p ON t.product_id = p.product_id\n"
        "WHERE po.premium_amount > (SELECT AVG(po3.premium_amount)\n"
        "                             FROM policy po3\n"
        "                             INNER JOIN coverage_tier t3 ON po3.tier_id = t3.tier_id\n"
        "                             WHERE t3.product_id = t.product_id)\n"
        "ORDER BY p.product_name, po.premium_amount DESC\n"
        "LIMIT 25;"),
}


STATUS_NAMES = {'Pending': 'Under review', 'Approved': 'Approved', 'Rejected': 'Declined'}


def _last_12_months():
    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append(f'{y:04d}-{m:02d}')
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(months))


@role_required('ADMIN')
def Dashboard(request):
    call_proc('sp_refresh_policy_status', [])
    kpis = call_proc_one('sp_dashboard_kpis', [])

    months = _last_12_months()
    prem = {r['period']: r for r in query_all(SQL['monthly_premium'])}
    pay = {r['period']: r for r in query_all(SQL['monthly_payout'])}
    monthly_rows = [{'period': m, 'label': date(int(m[:4]), int(m[5:]), 1).strftime('%b %Y'),
                     'premium': float(prem[m]['net_premium']) if m in prem else 0.0,
                     'payout': float(pay[m]['payout']) if m in pay else 0.0} for m in months]

    best = query_all(SQL['best_sellers'])
    status_rows = query_all(SQL['claim_status'])
    loss = query_all(SQL['loss_ratio'])
    ages = query_all(SQL['age_bands'])
    checkout = {r['result']: r for r in query_all(SQL['checkout'])}

    charts = {
        'monthly': {'labels': [r['label'] for r in monthly_rows],
                    'premium': [r['premium'] for r in monthly_rows],
                    'payout': [r['payout'] for r in monthly_rows]},
        'best': {'labels': [r['product_name'] for r in best], 'values': [int(r['sold']) for r in best]},
        'status': {'labels': [STATUS_NAMES.get(r['claim_status'], r['claim_status']) for r in status_rows],
                   'values': [int(r['n']) for r in status_rows]},
        'loss': {'labels': [r['product_name'] for r in loss],
                 'values': [float(r['loss_ratio_pct'] or 0) for r in loss]},
        'ages': {'labels': [r['age_band'] for r in ages], 'values': [int(r['policies']) for r in ages]},
    }
    context = {
        'kpis': kpis,
        'charts': charts,
        'monthlyRows': monthly_rows,
        'best': best,
        'statusRows': status_rows,
        'loss': loss,
        'ages': ages,
        'checkout': checkout,
        'topCustomers': query_all(SQL['top_customers']),
        'staff': query_all(SQL['staff']),
        'aboveAvg': query_all(SQL['above_avg']),
    }
    return render(request, 'analytics_template/dashboard.html', context)


@role_required('ADMIN')
def Reports(request):
    sales = query_all(REPORT_SQL['sales_rollup'])
    for r in sales:
        r['rollup'] = r['tier_name'] in ('Subtotal', '')
    monthly = query_all(REPORT_SQL['monthly_rollup'])
    for r in monthly:
        r['rollup'] = r['period'] == 'Grand total'
    claims = query_all(REPORT_SQL['claims_rollup'])
    for r in claims:
        r['rollup'] = r['claim_status'] in ('Subtotal', '')
    context = {
        'sales': sales,
        'monthly': monthly,
        'claims': claims,
        'renewals': query_all(REPORT_SQL['renewals']),
        'neverClaimed': query_all(REPORT_SQL['never_claimed']),
        'aboveAvg': query_all(REPORT_SQL['above_product_avg']),
    }
    return render(request, 'analytics_template/reports.html', context)
