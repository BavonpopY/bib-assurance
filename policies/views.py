"""
Module 4 : My Policies & Coverage Tracker
  - sp_get_my_policies reads vw_policy_overview (Lab 14 getorderdetail pattern)
  - live status (Active / Scheduled / Expired / Exhausted / Cancelled) comes from
    fn_policy_live_status(); sp_refresh_policy_status() saves it to the table
  - sp_cancel_policy: cancel + refund in one transaction (14-day free look)
"""
from datetime import date, timedelta

from django.contrib import messages
from django.shortcuts import redirect, render

from projectweb.dbhelper import (DatabaseError, call_proc, call_proc_one, db_error_message,
                                 query_all, query_one)
from projectweb.sessionhelper import role_required, signin_required

STATUSES = ['Active', 'Scheduled', 'Exhausted', 'Expired', 'Cancelled']


@role_required('CUSTOMER')
def MyPolicies(request):
    myUserID = request.session['signInUser']['user_id']
    myPolicyList = call_proc('sp_get_my_policies', [myUserID])
    status = request.GET.get('status', '')
    counts = {s: 0 for s in STATUSES}
    for p in myPolicyList:
        counts[p['live_status']] += 1
    if status in STATUSES:
        myPolicyList = [p for p in myPolicyList if p['live_status'] == status]
    context = {
        'myPolicyList': myPolicyList,
        'status': status,
        'counts': counts,
        'total': sum(counts.values()),
        'actionNeeded': query_all("SELECT * FROM vw_beneficiary_check WHERE user_id = %s "
                                  "AND allocation_status = 'Action needed' "
                                  "AND live_status IN ('Active', 'Scheduled', 'Exhausted')", [myUserID]),
        'inProgress': query_all("SELECT * FROM vw_quote_details WHERE user_id = %s "
                                "AND live_status IN ('Open', 'In review', 'Approved') "
                                "ORDER BY created_at DESC LIMIT 6", [myUserID]),
        'summary': query_one("SELECT IFNULL(SUM(coverage_amount), 0) AS coverage, "
                             "IFNULL(SUM(remaining_coverage), 0) AS remaining, "
                             "IFNULL(SUM(premium_amount), 0) AS premiums "
                             "FROM vw_policy_overview WHERE user_id = %s AND live_status IN ('Active', 'Exhausted')",
                             [myUserID]),
    }
    return render(request, 'policies_template/mypolicies.html', context)


@signin_required
def PolicyDetail(request, policyID):
    mySignInUser = request.session['signInUser']
    policy = query_one("SELECT * FROM vw_policy_overview WHERE policy_id = %s", [policyID])
    if policy is None or (mySignInUser['role'] == 'CUSTOMER' and policy['user_id'] != mySignInUser['user_id']):
        messages.error(request, 'We could not find that policy.')
        return redirect('myHomePage')

    can_cancel = (mySignInUser['role'] == 'CUSTOMER'
                  and policy['live_status'] in ('Active', 'Scheduled')
                  and policy['claim_count'] == 0
                  and policy['created_at'].date() >= date.today() - timedelta(days=14))
    context = {
        'policy': policy,
        'beneficiaries': query_all("SELECT * FROM policy_beneficiary WHERE policy_id = %s ORDER BY allocation_pct DESC",
                                   [policyID]),
        'check': query_one("SELECT * FROM vw_beneficiary_check WHERE policy_id = %s", [policyID]),
        'claims': query_all("SELECT * FROM vw_claim_details WHERE policy_id = %s ORDER BY submitted_at DESC", [policyID]),
        'payments': query_all("SELECT * FROM payment WHERE policy_id = %s ORDER BY paid_at", [policyID]),
        'ledger': query_all(
            "SELECT a.*, c.claim_number, CONCAT(u.first_name, ' ', u.last_name) AS changed_by_name "
            "FROM claim_status_audit AS a "
            "INNER JOIN claim AS c ON a.claim_id = c.claim_id "
            "LEFT OUTER JOIN app_user AS u ON a.changed_by = u.user_id "
            "WHERE a.policy_id = %s ORDER BY a.changedate, a.audit_id", [policyID]),
        'canCancel': can_cancel,
        'canClaim': (mySignInUser['role'] == 'CUSTOMER' and policy['live_status'] in ('Active', 'Expired')
                     and policy['remaining_coverage'] > 0 and date.today() <= policy['claim_deadline']),
    }
    return render(request, 'policies_template/policydetail.html', context)


@role_required('CUSTOMER')
def CancelPolicy(request, policyID):
    if request.method == 'POST':
        try:
            myResult = call_proc_one('sp_cancel_policy', [policyID, request.session['signInUser']['user_id']])
        except DatabaseError as e:
            messages.error(request, db_error_message(e))
        else:
            if myResult['status'] == 'SUCCESS':
                messages.success(request, myResult['message'])
            else:
                messages.error(request, myResult['message'])
    return redirect('myPolicyDetailPage', policyID=policyID)


@role_required('STAFF', 'ADMIN')
def AllPolicies(request):
    status = request.GET.get('status', '')
    product = request.GET.get('product', '')
    search = request.GET.get('q', '').strip()
    where, params = [], []
    if status in STATUSES:
        where.append("live_status = %s")
        params.append(status)
    if product:
        where.append("product_id = %s")
        params.append(product)
    if search:
        where.append("(policy_number LIKE %s OR customer_name LIKE %s OR customer_email LIKE %s)")
        params += [f'%{search}%'] * 3
    sql = "SELECT * FROM vw_policy_overview " + ("WHERE " + " AND ".join(where) + " " if where else "") + \
          "ORDER BY created_at DESC LIMIT 200"
    context = {
        'policies': query_all(sql, params or None),
        'statusCounts': query_all("SELECT live_status, COUNT(*) AS n FROM vw_policy_overview GROUP BY live_status "
                                  "ORDER BY FIELD(live_status, 'Active', 'Scheduled', 'Exhausted', 'Expired', 'Cancelled')"),
        'products': query_all("SELECT product_id, product_name FROM product ORDER BY product_name"),
        'status': status, 'product': product, 'q': search,
    }
    return render(request, 'policies_template/allpolicies.html', context)
