"""
Sign-in helpers.

Lab 14 stores the signed-in customer in request.session['signInUser'] and every
protected view starts with:

    mySignInUser = request.session.get('signInUser')
    if mySignInUser is None:
        return redirect('mySignInPage')

The two decorators below do exactly that (plus a role check), so each view
can simply be marked  @signin_required  or  @role_required('STAFF', 'ADMIN').

request.session['signInUser'] = {
    'user_id': 5, 'first_name': 'Somchai', 'last_name': 'Jaidee',
    'email': 'somchai@bib.test', 'role': 'CUSTOMER', 'avatar_path': '...'
}
"""
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

HOME_BY_ROLE = {
    'CUSTOMER': 'myPoliciesPage',
    'STAFF': 'myClaimQueuePage',
    'ADMIN': 'myDashboardPage',
}


def get_signin_user(request):
    return request.session.get('signInUser')


def _to_signin(request):
    messages.info(request, 'Please sign in to continue.')
    return redirect(f"{reverse('mySignInPage')}?{urlencode({'next': request.get_full_path()})}")


def signin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.session.get('signInUser') is None:
            return _to_signin(request)
        return view(request, *args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            mySignInUser = request.session.get('signInUser')
            if mySignInUser is None:
                return _to_signin(request)
            if mySignInUser.get('role') not in roles:
                messages.error(request, 'You do not have access to that page.')
                return redirect(HOME_BY_ROLE.get(mySignInUser.get('role'), 'myHomePage'))
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
