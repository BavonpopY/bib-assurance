"""
Module 5 : Claims Submission (with image evidence) & Approval Workflow
  - photos are saved with FileSystemStorage (LabExtra); only the path goes into
    claim_evidence.image_path
  - sp_submit_claim inserts claim + evidence in one transaction;
    trg_claim_before_insert validates dates / amounts with SIGNAL
  - sp_review_claim updates the claim; then
      trg_claim_before_update        -> approval rules
      trg_claim_after_update         -> DEDUCTS approved amount from policy.remaining_coverage
      trg_claim_after_update_audit   -> writes claim_status_audit (FOLLOWS)
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import redirect, render

from projectweb.dbhelper import (DatabaseError, call_proc, call_proc_one, db_error_message,
                                 execute, query_all, query_one)
from projectweb.filehelper import delete_uploaded, save_image
from projectweb.sessionhelper import role_required, signin_required


def _claim_for(request, claimID):
    mySignInUser = request.session['signInUser']
    claim = query_one("SELECT * FROM vw_claim_details WHERE claim_id = %s", [claimID])
    if claim is None or (mySignInUser['role'] == 'CUSTOMER' and claim['user_id'] != mySignInUser['user_id']):
        return None
    return claim


@role_required('CUSTOMER')
def MyClaims(request):
    myUserID = request.session['signInUser']['user_id']
    context = {
        'myClaimList': query_all("SELECT * FROM vw_claim_details WHERE user_id = %s ORDER BY submitted_at DESC", [myUserID]),
        'summary': query_one("SELECT COUNT(*) AS n, IFNULL(SUM(c.claim_status = 'Pending'), 0) AS pending, "
                             "IFNULL(SUM(c.approved_amount), 0) AS paid "
                             "FROM claim AS c INNER JOIN policy AS p ON c.policy_id = p.policy_id "
                             "WHERE p.user_id = %s", [myUserID]),
    }
    return render(request, 'claims_template/myclaims.html', context)


@role_required('CUSTOMER')
def SubmitClaim(request):
    myUserID = request.session['signInUser']['user_id']
    eligible = query_all(
        "SELECT policy_id, policy_number, product_name, tier_name, thumbnail_path, start_date, end_date, "
        "coverage_amount, remaining_coverage, deductible, claim_deadline, live_status "
        "FROM vw_policy_overview "
        "WHERE user_id = %s AND live_status IN ('Active', 'Expired') "
        "AND remaining_coverage > 0 AND CURDATE() <= claim_deadline "
        "ORDER BY FIELD(live_status, 'Active', 'Expired'), end_date DESC", [myUserID])
    context = {'eligible': eligible, 'today': date.today(),
               'form': {'policy_id': request.GET.get('policy', '')}}

    if request.method == 'POST':
        myData = request.POST.copy()
        form = {k: myData.get(k, '').strip() for k in
                ('policy_id', 'incident_date', 'incident_title', 'incident_description', 'claimed_amount',
                 'caption1', 'caption2', 'caption3')}
        context['form'] = form
        error = None
        if '' in (form['policy_id'], form['incident_date'], form['incident_title'],
                  form['incident_description'], form['claimed_amount']):
            error = 'Please complete all required fields.'
        try:
            amount = Decimal(form['claimed_amount'] or '0')
            if amount <= 0:
                error = error or 'The claimed amount must be greater than zero.'
        except InvalidOperation:
            error = error or 'Please enter the claimed amount in Thai Baht.'
        files = [request.FILES.get(f'evidence{i}') for i in (1, 2, 3)]
        if files[0] is None:
            error = error or 'Please attach at least one supporting document, such as a medical certificate or an itemised hospital bill.'
        if error:
            messages.error(request, error)
            return render(request, 'claims_template/submitclaim.html', context)

        saved = []
        for f in files:
            if f is None:
                saved.append(None)
                continue
            path, err = save_image(f, 'claim')
            if err:
                for p in saved:
                    delete_uploaded(p)
                messages.error(request, err)
                return render(request, 'claims_template/submitclaim.html', context)
            saved.append(path)
        # move the uploads to the front so evidence #1 is never empty
        pairs = [(p, form[f'caption{i + 1}']) for i, p in enumerate(saved) if p]
        pairs += [(None, None)] * (3 - len(pairs))

        try:
            myResult = call_proc_one('sp_submit_claim', [
                myUserID, int(form['policy_id']), form['incident_date'], form['incident_title'],
                form['incident_description'], amount,
                pairs[0][0], pairs[0][1], pairs[1][0], pairs[1][1], pairs[2][0], pairs[2][1], None])
        except DatabaseError as e:           # trg_claim_before_insert SIGNALs
            myResult = {'status': 'ERROR', 'message': db_error_message(e)}
        if myResult['status'] != 'SUCCESS':
            for p in saved:
                delete_uploaded(p)
            messages.error(request, myResult['message'])
            return render(request, 'claims_template/submitclaim.html', context)
        messages.success(request, myResult['message'])
        return redirect('myClaimDetailPage', claimID=myResult['claim_id'])

    return render(request, 'claims_template/submitclaim.html', context)


@signin_required
def ClaimDetail(request, claimID):
    claim = _claim_for(request, claimID)
    if claim is None:
        messages.error(request, 'We could not find that claim.')
        return redirect('myHomePage')
    context = {
        'claim': claim,
        'evidence': query_all("SELECT * FROM claim_evidence WHERE claim_id = %s ORDER BY evidence_id", [claimID]),
        'audit': query_all("SELECT a.*, CONCAT(u.first_name, ' ', u.last_name) AS changed_by_name "
                           "FROM claim_status_audit AS a LEFT OUTER JOIN app_user AS u ON a.changed_by = u.user_id "
                           "WHERE a.claim_id = %s ORDER BY a.changedate, a.audit_id", [claimID]),
    }
    return render(request, 'claims_template/claimdetail.html', context)


@role_required('CUSTOMER')
def WithdrawClaim(request, claimID):
    claim = _claim_for(request, claimID)
    if request.method == 'POST' and claim is not None:
        paths = [e['image_path'] for e in query_all("SELECT image_path FROM claim_evidence WHERE claim_id = %s", [claimID])]
        try:
            execute("DELETE FROM claim WHERE claim_id = %s", [claimID])   # trg_claim_before_delete guards it
        except DatabaseError as e:
            messages.error(request, db_error_message(e))
            return redirect('myClaimDetailPage', claimID=claimID)
        for p in paths:
            delete_uploaded(p)
        messages.success(request, f"Claim {claim['claim_number']} has been withdrawn.")
    return redirect('myClaimsPage')


@role_required('STAFF', 'ADMIN')
def ClaimQueue(request):
    status = request.GET.get('status', 'Pending')
    if status not in ('Pending', 'Approved', 'Rejected', 'All'):
        status = 'Pending'
    context = {
        'claims': call_proc('sp_get_claim_queue', [status]),
        'status': status,
        'counts': {r['claim_status']: r['n'] for r in
                   query_all("SELECT claim_status, COUNT(*) AS n FROM claim GROUP BY claim_status")},
        'oldest': query_one("SELECT MAX(hours_open) AS h FROM vw_claim_details WHERE claim_status = 'Pending'"),
    }
    return render(request, 'claims_template/claimqueue.html', context)


@role_required('STAFF', 'ADMIN')
def ReviewClaim(request, claimID):
    claim = query_one("SELECT * FROM vw_claim_details WHERE claim_id = %s", [claimID])
    if claim is None:
        messages.error(request, 'We could not find that claim.')
        return redirect('myClaimQueuePage')

    if request.method == 'POST':
        myData = request.POST.copy()
        decision = myData.get('decision')
        note = myData.get('review_note', '').strip()
        amount = None
        if decision == 'Approved':
            try:
                amount = Decimal(myData.get('approved_amount', ''))
            except InvalidOperation:
                messages.error(request, 'Please enter the approved amount in Thai Baht.')
                return redirect('myReviewClaimPage', claimID=claimID)
        try:
            myResult = call_proc_one('sp_review_claim', [claimID, request.session['signInUser']['user_id'],
                                                         decision, amount, note, None])
        except DatabaseError as e:          # trg_claim_before_update SIGNALs
            messages.error(request, db_error_message(e))
            return redirect('myReviewClaimPage', claimID=claimID)
        if myResult['status'] == 'SUCCESS':
            messages.success(request, myResult['message'])
            return redirect('myClaimQueuePage')
        messages.error(request, myResult['message'])
        return redirect('myReviewClaimPage', claimID=claimID)

    context = {
        'claim': claim,
        'evidence': query_all("SELECT * FROM claim_evidence WHERE claim_id = %s ORDER BY evidence_id", [claimID]),
        'history': query_all("SELECT claim_id, claim_number, incident_title, claimed_amount, approved_amount, "
                             "claim_status, submitted_at FROM vw_claim_details "
                             "WHERE user_id = %s AND claim_id <> %s ORDER BY submitted_at DESC LIMIT 6",
                             [claim['user_id'], claimID]),
        'audit': query_all("SELECT a.*, CONCAT(u.first_name, ' ', u.last_name) AS changed_by_name "
                           "FROM claim_status_audit AS a LEFT OUTER JOIN app_user AS u ON a.changed_by = u.user_id "
                           "WHERE a.claim_id = %s ORDER BY a.changedate, a.audit_id", [claimID]),
        'approveNotes': ['Approved in accordance with the policy schedule.',
                         'Approved after review of the itemised invoice and medical report.',
                         'Approved less the policy deductible.',
                         'Approved in full. Lump-sum benefit paid on confirmed diagnosis.'],
        'rejectNotes': ['The condition is pre-existing and excluded under the policy terms.',
                        'Treatment was received during the policy waiting period.',
                        'Expenses are not medically necessary according to the attending physician\'s report.',
                        'Supporting documents are incomplete. Please resubmit with an itemised invoice.',
                        'The injury was not caused by an accident as defined in the policy.'],
    }
    return render(request, 'claims_template/reviewclaim.html', context)
