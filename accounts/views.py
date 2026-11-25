"""
Module 1 : Authentication, Role Management & Beneficiaries
  - SignIn / Register use raw SQL + request.session exactly like Lab 14
    (passwords are hashed with Django's own make_password / check_password)
  - sp_register_user  (EXIT HANDLER FOR 1062, trigger 18+ check)
  - sp_save_beneficiaries (transaction: COMMIT only when total = 100%)
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.db import connection
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from projectweb.dbhelper import (DatabaseError, call_proc_one, db_error_message,
                                 execute, query_all, query_one)
from projectweb.filehelper import delete_uploaded, save_image
from projectweb.sessionhelper import HOME_BY_ROLE, role_required, signin_required


def SignIn(request):
    context = {}
    mySignInUser = request.session.get('signInUser')
    if mySignInUser is not None:
        return redirect(HOME_BY_ROLE[mySignInUser['role']])

    if request.method == 'POST':
        myData = request.POST.copy()
        myEmail = myData.get('myEmail', '').strip().lower()
        myPassword = myData.get('myPassword', '')
        context['myEmail'] = myEmail
        with connection.cursor() as myCursor:
            myCursor.execute("SELECT u.user_id, u.first_name, u.last_name, u.email, r.role_code, "
                             "u.avatar_path, u.password_hash, u.is_active "
                             "FROM app_user AS u INNER JOIN role AS r ON u.role_id = r.role_id "
                             "WHERE u.email = %s", [myEmail])
            myFetchData = myCursor.fetchall()

        if len(myFetchData) > 0 and myFetchData[0][7] == 1 and check_password(myPassword, myFetchData[0][6]):
            row = myFetchData[0]
            print('Sign-in Successfully', row[3], row[4])
            request.session['signInUser'] = {
                'user_id': row[0], 'first_name': row[1], 'last_name': row[2],
                'email': row[3], 'role': row[4], 'avatar_path': row[5],
            }
            with connection.cursor() as myCursor:
                myCursor.execute("UPDATE app_user SET last_login_at = NOW() WHERE user_id = %s", [row[0]])
                myCursor.callproc('sp_refresh_policy_status', [])
            messages.success(request, f'Welcome back, {row[1]}.')
            next_url = request.GET.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect(HOME_BY_ROLE[row[4]])

        print('Sign-in Error')
        if len(myFetchData) > 0 and myFetchData[0][7] == 0:
            context['returnMessage'] = 'This account is inactive. Please contact BIB Assurance customer service.'
        else:
            context['returnMessage'] = 'The e-mail address or password is incorrect.'
    return render(request, 'accounts_template/signin.html', context)


def SignOut(request):
    request.session.flush()
    messages.info(request, 'You have been signed out securely.')
    return redirect('myHomePage')


def Register(request):
    context = {'today': date.today()}
    if request.method == 'POST':
        myData = request.POST.copy()
        form = {k: myData.get(k, '').strip() for k in
                ('myFirstName', 'myLastName', 'myEmail', 'myPhone', 'myDOB')}
        myPassword = myData.get('myPassword', '')
        myConfirm = myData.get('myConfirmPassword', '')
        context['form'] = form

        if '' in (form['myFirstName'], form['myLastName'], form['myEmail'], form['myDOB'], myPassword):
            context['returnMessage'] = 'Please complete all required fields.'
        elif len(myPassword) < 8:
            context['returnMessage'] = 'Your password must contain at least 8 characters.'
        elif myPassword != myConfirm:
            context['returnMessage'] = 'The passwords do not match.'
        else:
            try:
                myResult = call_proc_one('sp_register_user', [
                    'CUSTOMER', form['myFirstName'], form['myLastName'], form['myEmail'].lower(),
                    make_password(myPassword), form['myPhone'], form['myDOB'],
                ])
            except DatabaseError as e:            # e.g. trigger: under 18
                context['returnMessage'] = db_error_message(e)
            else:
                if myResult['status'] == 'SUCCESS':
                    messages.success(request, myResult['message'])
                    return redirect('mySignInPage')
                context['returnMessage'] = myResult['message']
    return render(request, 'accounts_template/register.html', context)


@signin_required
def Profile(request):
    mySignInUser = request.session['signInUser']
    myUserID = mySignInUser['user_id']

    if request.method == 'POST':
        myData = request.POST.copy()
        if 'save_profile' in myData:
            first = myData.get('first_name', '').strip()
            last = myData.get('last_name', '').strip()
            phone = myData.get('phone', '').strip() or None
            dob = myData.get('date_of_birth') or None
            if not first or not last:
                messages.error(request, 'Please enter your first and last name.')
            else:
                try:
                    execute("UPDATE app_user SET first_name = %s, last_name = %s, phone = %s, "
                            "date_of_birth = %s WHERE user_id = %s", [first, last, phone, dob, myUserID])
                    mySignInUser.update(first_name=first, last_name=last)
                    request.session['signInUser'] = mySignInUser
                    messages.success(request, 'Your personal details have been updated.')
                except DatabaseError as e:     # trg_app_user_before_update (18+)
                    messages.error(request, db_error_message(e))

        elif 'upload_avatar' in myData:
            path, error = save_image(request.FILES.get('avatar'), 'avatar')
            if error:
                messages.error(request, error)
            else:
                old = query_one("SELECT avatar_path FROM app_user WHERE user_id = %s", [myUserID])
                execute("UPDATE app_user SET avatar_path = %s WHERE user_id = %s", [path, myUserID])
                delete_uploaded(old['avatar_path'] if old else None)
                mySignInUser['avatar_path'] = path
                request.session['signInUser'] = mySignInUser
                messages.success(request, 'Your profile photo has been updated.')

        elif 'change_password' in myData:
            row = query_one("SELECT password_hash FROM app_user WHERE user_id = %s", [myUserID])
            new = myData.get('new_password', '')
            if not check_password(myData.get('current_password', ''), row['password_hash']):
                messages.error(request, 'Your current password is incorrect.')
            elif len(new) < 8 or new != myData.get('confirm_password', ''):
                messages.error(request, 'The new passwords must match and contain at least 8 characters.')
            else:
                execute("UPDATE app_user SET password_hash = %s WHERE user_id = %s", [make_password(new), myUserID])
                messages.success(request, 'Your password has been changed.')
        return redirect('myProfilePage')

    context = {
        'me': query_one("SELECT u.*, r.role_name, r.role_code, fn_age(u.date_of_birth, CURDATE()) AS age "
                        "FROM app_user AS u INNER JOIN role AS r ON u.role_id = r.role_id "
                        "WHERE u.user_id = %s", [myUserID]),
        'stats': query_one("SELECT "
                           "(SELECT COUNT(*) FROM policy WHERE user_id = %s) AS policies, "
                           "(SELECT COUNT(*) FROM claim c INNER JOIN policy p ON c.policy_id = p.policy_id "
                           "  WHERE p.user_id = %s) AS claims, "
                           "(SELECT COUNT(*) FROM claim WHERE reviewed_by = %s) AS reviewed",
                           [myUserID, myUserID, myUserID]),
    }
    return render(request, 'accounts_template/profile.html', context)


@role_required('CUSTOMER')
def ManageBeneficiaries(request, policyID):
    myUserID = request.session['signInUser']['user_id']
    policy = query_one("SELECT * FROM vw_policy_overview WHERE policy_id = %s AND user_id = %s",
                       [policyID, myUserID])
    if policy is None:
        messages.error(request, 'We could not find that policy.')
        return redirect('myPoliciesPage')

    rows = [{'name': '', 'relationship': '', 'pct': ''} for _ in range(4)]
    current = query_all("SELECT full_name, relationship, allocation_pct FROM policy_beneficiary "
                        "WHERE policy_id = %s ORDER BY beneficiary_id", [policyID])
    for i, b in enumerate(current[:4]):
        rows[i] = {'name': b['full_name'], 'relationship': b['relationship'], 'pct': b['allocation_pct'].normalize()}

    if request.method == 'POST':
        myData = request.POST.copy()
        args, rows, error, names = [policyID, myUserID], [], None, set()
        for i in range(1, 5):
            name = myData.get(f'name{i}', '').strip()
            rel = myData.get(f'relationship{i}', '').strip()
            pct_raw = myData.get(f'pct{i}', '').strip()
            rows.append({'name': name, 'relationship': rel, 'pct': pct_raw})
            pct = None
            if name:
                if name.lower() in names:
                    error = f'{name} is listed more than once.'
                names.add(name.lower())
                if not rel:
                    error = error or f'Please choose a relationship for {name}.'
                try:
                    pct = Decimal(pct_raw)
                except InvalidOperation:
                    error = error or f'The benefit share for {name} must be a number.'
            args += [name or None, rel or None, pct]
        if error:
            messages.error(request, error)
        else:
            try:
                myResult = call_proc_one('sp_save_beneficiaries', args)
            except DatabaseError as e:      # trigger: > 100% running total or > 4 people
                messages.error(request, db_error_message(e))
            else:
                if myResult['status'] == 'SUCCESS':
                    messages.success(request, myResult['message'])
                    return redirect('myPolicyDetailPage', policyID=policyID)
                messages.error(request, myResult['message'])

    context = {
        'policy': policy,
        'rows': rows,
        'check': query_one("SELECT * FROM vw_beneficiary_check WHERE policy_id = %s", [policyID]),
        'relationships': ['Spouse', 'Father', 'Mother', 'Son', 'Daughter', 'Brother', 'Sister',
                          'Grandparent', 'Grandchild', 'Relative', 'Legal guardian'],
    }
    return render(request, 'accounts_template/beneficiaries.html', context)


@role_required('ADMIN')
def UserManagement(request):
    myAdminID = request.session['signInUser']['user_id']
    if request.method == 'POST':
        myData = request.POST.copy()
        target = int(myData.get('user_id', 0))
        try:
            if target == myAdminID:
                messages.error(request, 'You cannot change the role or status of your own account.')
            elif 'set_role' in myData:
                execute("UPDATE app_user SET role_id = (SELECT role_id FROM role WHERE role_code = %s) "
                        "WHERE user_id = %s", [myData.get('role_code'), target])
                messages.success(request, 'The user role has been updated.')
            elif 'toggle_active' in myData:
                execute("UPDATE app_user SET is_active = 1 - is_active WHERE user_id = %s", [target])
                messages.success(request, 'The account status has been updated.')
        except DatabaseError as e:          # e.g. making a staff member a CUSTOMER without DOB
            messages.error(request, db_error_message(e))
        return redirect(f"{request.path}?role={request.GET.get('role', '')}")

    role = request.GET.get('role', '')
    params = [role] if role else None
    users = query_all(
        "SELECT u.user_id, u.first_name, u.last_name, u.email, u.phone, u.avatar_path, u.is_active, "
        "u.created_at, u.last_login_at, r.role_code, r.role_name, "
        "(SELECT COUNT(*) FROM policy p WHERE p.user_id = u.user_id) AS policies, "
        "(SELECT COUNT(*) FROM claim c WHERE c.reviewed_by = u.user_id) AS reviews "
        "FROM app_user AS u INNER JOIN role AS r ON u.role_id = r.role_id "
        + ("WHERE r.role_code = %s " if role else "") +
        "ORDER BY FIELD(r.role_code, 'ADMIN', 'STAFF', 'CUSTOMER'), u.first_name", params)
    context = {
        'users': users,
        'role': role,
        'roles': ['CUSTOMER', 'STAFF', 'ADMIN'],
        'roleCounts': query_all("SELECT r.role_code, COUNT(u.user_id) AS n FROM role r "
                                "LEFT OUTER JOIN app_user u ON u.role_id = r.role_id "
                                "GROUP BY r.role_code ORDER BY r.role_code"),
    }
    return render(request, 'accounts_template/users.html', context)


@role_required('ADMIN')
def AddStaff(request):
    context = {}
    if request.method == 'POST':
        myData = request.POST.copy()
        form = {k: myData.get(k, '').strip() for k in ('first_name', 'last_name', 'email', 'phone', 'role_code')}
        context['form'] = form
        password = myData.get('password', '')
        if '' in (form['first_name'], form['last_name'], form['email']) or len(password) < 8:
            context['returnMessage'] = 'Please enter a name, an e-mail address and a password of at least 8 characters.'
        elif form['role_code'] not in ('STAFF', 'ADMIN'):
            context['returnMessage'] = 'Please choose Claims Officer or Administrator.'
        else:
            try:
                myResult = call_proc_one('sp_register_user', [
                    form['role_code'], form['first_name'], form['last_name'], form['email'].lower(),
                    make_password(password), form['phone'], None])
            except DatabaseError as e:
                context['returnMessage'] = db_error_message(e)
            else:
                if myResult['status'] == 'SUCCESS':
                    messages.success(request, f"An account has been created for {form['first_name']} {form['last_name']}.")
                    return redirect('myUserManagementPage')
                context['returnMessage'] = myResult['message']
    return render(request, 'accounts_template/addstaff.html', context)
