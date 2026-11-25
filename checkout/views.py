"""
Module 3 : Underwriting application, Policy Purchase & ACID Checkout
  Buying is a 3-step process:
    1) sp_submit_application  : application + ID card + proof of occupation
                                (one transaction, trg_application_before_insert)
    2) sp_review_application  : an officer approves or declines
                                (trg_application_before_update / after_update)
    3) sp_checkout_policy     : payment, only possible for an approved application
  sp_checkout_policy does everything inside ONE transaction (Lab 4):
    START TRANSACTION
      INSERT policy -> UPDATE policy_number -> INSERT payment
      -> UPDATE premium_quote (Converted) -> INSERT checkout_log
    COMMIT
  The decline test card (see README) makes the procedure ROLLBACK after the
  policy row was already inserted; the customer only sees a "payment declined"
  notice - the technical proof is shown in MySQL Workbench, not on the page.
"""
from datetime import date, timedelta

from django.contrib import messages
from django.shortcuts import redirect, render

from projectweb.dbhelper import (DatabaseError, call_proc, call_proc_one, db_error_message, query_all,
                                  query_one)
from projectweb.filehelper import delete_uploaded, save_image
from projectweb.sessionhelper import role_required, signin_required

INCOME_BANDS = ['Below 15,000', '15,000-30,000', '30,001-50,000', '50,001-100,000', 'Above 100,000']
EXTRA_TYPES = [('Income', 'Salary slip or bank statement'), ('Medical', 'Health check-up report'),
               ('Other', 'Other supporting document')]
APPROVE_NOTES = ['Identity and occupation verified.', 'Documents verified. Standard terms apply.',
                 'Occupation class confirmed by employer certificate.']
REJECT_NOTES = ['The occupation stated in the documents does not match the selected occupation class. '
                'Please request a new quotation.',
                'The declared medical history requires a full medical examination before cover can be offered.',
                'The proof of occupation is not legible. Please apply again with a clear copy.',
                'The sum insured is too high relative to the declared income.']

@role_required('CUSTOMER')
def Checkout(request, quoteID):
    myUserID = request.session['signInUser']['user_id']
    quote = query_one("SELECT * FROM vw_quote_details WHERE quote_id = %s AND user_id = %s", [quoteID, myUserID])
    if quote is None:
        messages.error(request, 'We could not find that quotation.')
        return redirect('myProductListPage')

    if quote['live_status'] != 'Approved':
        # underwriting first: the application must be approved before payment
        if quote['live_status'] == 'Open':
            messages.info(request, 'Please submit your application documents before payment.')
            return redirect('myApplicationFormPage', quoteID=quoteID)
        if quote['live_status'] == 'In review':
            messages.info(request, 'Your application is still being reviewed. You can pay once it has been approved.')
        elif quote['live_status'] == 'Converted':
            messages.info(request, 'A policy has already been issued for this quotation.')
        return redirect('myQuoteDetailPage', quoteID=quoteID)

    today = date.today()
    context = {
        'quote': quote,
        'minStart': today,
        'maxStart': today + timedelta(days=30),
        'form': {'payment_method': 'Card', 'start_date': today.isoformat()},
    }

    if request.method == 'POST':
        myData = request.POST.copy()
        method = myData.get('payment_method', '')
        card = myData.get('card_number', '')
        start = myData.get('start_date') or None
        context['form'] = {'payment_method': method, 'card_number': card, 'start_date': start}
        try:
            myResult = call_proc_one('sp_checkout_policy', [quoteID, myUserID, method, card, start])
        except DatabaseError as e:
            messages.error(request, db_error_message(e))
            return render(request, 'checkout_template/checkout.html', context)

        if myResult['status'] == 'SUCCESS':
            messages.success(request, myResult['message'])
            return redirect('myCheckoutSuccessPage', policyID=myResult['policy_id'])

        if myResult['status'] == 'DECLINED':
            context['declined'] = myResult['message']
            context['form']['card_number'] = ''
        else:
            messages.error(request, myResult['message'])
        context['quote'] = query_one("SELECT * FROM vw_quote_details WHERE quote_id = %s", [quoteID])

    return render(request, 'checkout_template/checkout.html', context)


@role_required('CUSTOMER')
def CheckoutSuccess(request, policyID):
    myUserID = request.session['signInUser']['user_id']
    policy = query_one("SELECT * FROM vw_policy_overview WHERE policy_id = %s AND user_id = %s", [policyID, myUserID])
    if policy is None:
        return redirect('myPoliciesPage')
    context = {
        'policy': policy,
        'payment': query_one("SELECT * FROM payment WHERE policy_id = %s ORDER BY payment_id DESC LIMIT 1", [policyID]),
    }
    return render(request, 'checkout_template/success.html', context)


@role_required('CUSTOMER')
def PaymentHistory(request):
    myUserID = request.session['signInUser']['user_id']
    context = {
        'payments': query_all(
            "SELECT pay.*, po.policy_number, po.policy_id, p.product_name, p.thumbnail_path, t.tier_name "
            "FROM payment AS pay "
            "INNER JOIN policy AS po ON pay.policy_id = po.policy_id "
            "INNER JOIN coverage_tier AS t ON po.tier_id = t.tier_id "
            "INNER JOIN product AS p ON t.product_id = p.product_id "
            "WHERE pay.user_id = %s ORDER BY pay.paid_at DESC", [myUserID]),
        'totals': query_one(
            "SELECT IFNULL(SUM(IF(payment_status = 'Paid', amount, 0)), 0) AS paid, "
            "IFNULL(SUM(IF(payment_status = 'Refunded', amount, 0)), 0) AS refunded, COUNT(*) AS n "
            "FROM payment WHERE user_id = %s", [myUserID]),
        'attempts': query_all(
            "SELECT l.*, q.quote_id FROM checkout_log AS l "
            "LEFT OUTER JOIN premium_quote AS q ON l.quote_id = q.quote_id "
            "WHERE l.user_id = %s AND l.result <> 'SUCCESS' ORDER BY l.attempted_at DESC LIMIT 10", [myUserID]),
    }
    return render(request, 'checkout_template/payments.html', context)


@role_required('ADMIN')
def CheckoutLog(request):
    result = request.GET.get('result', '')
    params = [result] if result else None
    context = {
        'result': result,
        'summary': query_all("SELECT result, COUNT(*) AS n, IFNULL(SUM(amount), 0) AS amount "
                             "FROM checkout_log GROUP BY result ORDER BY result"),
        'logs': query_all(
            "SELECT l.*, CONCAT(u.first_name, ' ', u.last_name) AS customer_name, po.policy_number "
            "FROM checkout_log AS l "
            "INNER JOIN app_user AS u ON l.user_id = u.user_id "
            "LEFT OUTER JOIN policy AS po ON l.policy_id = po.policy_id "
            + ("WHERE l.result = %s " if result else "") +
            "ORDER BY l.attempted_at DESC LIMIT 150", params),
    }
    return render(request, 'checkout_template/checkoutlog.html', context)



# ------------------------------------------------------------- underwriting
def _application_or_none(request, applicationID):
    mySignInUser = request.session['signInUser']
    app = query_one("SELECT * FROM vw_application_details WHERE application_id = %s", [applicationID])
    if app is None or (mySignInUser['role'] == 'CUSTOMER' and app['user_id'] != mySignInUser['user_id']):
        return None
    return app


def _documents(applicationID):
    return query_all("SELECT document_id, document_type, image_path, caption, uploaded_at "
                     "FROM application_document WHERE application_id = %s ORDER BY document_id", [applicationID])


@role_required('CUSTOMER')
def ApplicationForm(request, quoteID):
    myUserID = request.session['signInUser']['user_id']
    quote = query_one("SELECT * FROM vw_quote_details WHERE quote_id = %s AND user_id = %s", [quoteID, myUserID])
    if quote is None:
        messages.error(request, 'We could not find that quotation.')
        return redirect('myProductListPage')
    if quote['application_id']:
        return redirect('myApplicationDetailPage', applicationID=quote['application_id'])
    if quote['live_status'] != 'Open':
        messages.error(request, 'This quotation is no longer available. Please request a new quotation.')
        return redirect('myQuoteDetailPage', quoteID=quoteID)

    # pre-fill from the customer's previous application (people rarely change jobs)
    last = query_one("SELECT occupation, employer, monthly_income, is_smoker FROM underwriting_application "
                     "WHERE user_id = %s ORDER BY submitted_at DESC LIMIT 1", [myUserID]) or {}
    form = {'occupation': last.get('occupation', ''), 'employer': last.get('employer') or '',
            'monthly_income': last.get('monthly_income', ''), 'is_smoker': str(last.get('is_smoker', '')),
            'has_medical_history': '', 'health_details': '', 'extra_type': 'Income',
            'id_caption': '', 'occupation_caption': '', 'extra_caption': ''}
    context = {'quote': quote, 'form': form, 'incomeBands': INCOME_BANDS, 'extraTypes': EXTRA_TYPES}

    if request.method == 'POST':
        myData = request.POST.copy()
        form.update({k: myData.get(k, '').strip() for k in form})
        context['form'] = form
        error = None
        if not form['occupation'] or form['monthly_income'] not in INCOME_BANDS:
            error = 'Please enter your occupation and select your monthly income.'
        elif form['is_smoker'] not in ('0', '1') or form['has_medical_history'] not in ('0', '1'):
            error = 'Please answer both health questions.'
        elif form['has_medical_history'] == '1' and len(form['health_details']) < 5:
            error = 'Please describe your medical history.'
        elif 'id_document' not in request.FILES or 'occupation_document' not in request.FILES:
            error = 'Please attach a copy of your ID card and a proof of occupation.'

        saved = []
        if error is None:
            for field in ('id_document', 'occupation_document', 'extra_document'):
                if field in request.FILES:
                    path, err = save_image(request.FILES[field], 'application')
                    if err:
                        error = err
                        break
                    saved.append((field, path))
        if error:
            for _, path in saved:
                delete_uploaded(path)
            messages.error(request, error)
            return render(request, 'checkout_template/applicationform.html', context)

        files = dict(saved)
        extra_type = form['extra_type'] if form['extra_type'] in dict(EXTRA_TYPES) else 'Other'
        try:
            myResult = call_proc_one('sp_submit_application', [
                myUserID, quoteID, form['occupation'], form['employer'], form['monthly_income'],
                int(form['is_smoker']), int(form['has_medical_history']), form['health_details'],
                files['id_document'], form['id_caption'] or 'Copy of ID card',
                files['occupation_document'], form['occupation_caption'] or 'Proof of occupation',
                extra_type if 'extra_document' in files else None, files.get('extra_document'),
                form['extra_caption'] or dict(EXTRA_TYPES)[extra_type] if 'extra_document' in files else None,
                None])
        except DatabaseError as e:
            myResult = {'status': 'ERROR', 'message': db_error_message(e)}
        if myResult['status'] == 'SUCCESS':
            messages.success(request, myResult['message'])
            return redirect('myApplicationDetailPage', applicationID=myResult['application_id'])
        for _, path in saved:
            delete_uploaded(path)
        messages.error(request, myResult['message'])

    return render(request, 'checkout_template/applicationform.html', context)


@signin_required
def ApplicationDetail(request, applicationID):
    app = _application_or_none(request, applicationID)
    if app is None:
        messages.error(request, 'We could not find that application.')
        return redirect('myHomePage')
    if request.session['signInUser']['role'] != 'CUSTOMER':
        return redirect('myReviewApplicationPage', applicationID=applicationID)
    context = {
        'app': app,
        'quote': query_one("SELECT * FROM vw_quote_details WHERE quote_id = %s", [app['quote_id']]),
        'evidence': _documents(applicationID),
    }
    return render(request, 'checkout_template/applicationdetail.html', context)


@role_required('CUSTOMER')
def MyApplications(request):
    myUserID = request.session['signInUser']['user_id']
    context = {
        'applications': query_all(
            "SELECT a.*, q.live_status AS quote_live_status, q.expires_at "
            "FROM vw_application_details AS a "
            "INNER JOIN vw_quote_details AS q ON a.quote_id = q.quote_id "
            "WHERE a.user_id = %s ORDER BY a.submitted_at DESC", [myUserID]),
        'awaiting': query_all("SELECT * FROM vw_quote_details WHERE user_id = %s AND live_status = 'Open' "
                              "ORDER BY created_at DESC", [myUserID]),
    }
    return render(request, 'checkout_template/myapplications.html', context)


@role_required('STAFF', 'ADMIN')
def ApplicationQueue(request):
    status = request.GET.get('status', 'Pending')
    if status not in ('Pending', 'Approved', 'Rejected', 'All'):
        status = 'Pending'
    context = {
        'status': status,
        'applications': call_proc('sp_get_application_queue', [status]),
        'counts': {r['app_status']: r['n'] for r in query_all(
            "SELECT app_status, COUNT(*) AS n FROM underwriting_application GROUP BY app_status")},
        'oldest': query_one("SELECT MAX(hours_open) AS h FROM vw_application_details WHERE app_status = 'Pending'"),
    }
    return render(request, 'checkout_template/applicationqueue.html', context)


@role_required('STAFF', 'ADMIN')
def ReviewApplication(request, applicationID):
    app = _application_or_none(request, applicationID)
    if app is None:
        messages.error(request, 'We could not find that application.')
        return redirect('myApplicationQueuePage')

    if request.method == 'POST' and app['app_status'] == 'Pending':
        decision = request.POST.get('decision', '')
        note = request.POST.get('review_note', '').strip()
        try:
            myResult = call_proc_one('sp_review_application', [
                applicationID, request.session['signInUser']['user_id'], decision, note, None])
        except DatabaseError as e:
            myResult = {'status': 'ERROR', 'message': db_error_message(e)}
        if myResult['status'] == 'SUCCESS':
            messages.success(request, myResult['message'])
            return redirect('myApplicationQueuePage')
        messages.error(request, myResult['message'])
        app = _application_or_none(request, applicationID)

    context = {
        'app': app,
        'evidence': _documents(applicationID),
        'policies': query_all("SELECT policy_id, policy_number, product_name, tier_name, coverage_amount, live_status "
                              "FROM vw_policy_overview WHERE user_id = %s ORDER BY start_date DESC LIMIT 8",
                              [app['user_id']]),
        'history': query_all("SELECT application_id, application_number, product_name, app_status, submitted_at "
                             "FROM vw_application_details WHERE user_id = %s AND application_id <> %s "
                             "ORDER BY submitted_at DESC LIMIT 6", [app['user_id'], applicationID]),
        'approveNotes': APPROVE_NOTES,
        'rejectNotes': REJECT_NOTES,
    }
    return render(request, 'checkout_template/reviewapplication.html', context)
