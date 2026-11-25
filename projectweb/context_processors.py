"""Values every template can use (navigation bar, footer, staff badge).

baseLayout decides which layout a shared page (profile, policy, claim) extends:
customers get the public site layout, claims officers and administrators get
the back-office layout with the sidebar.
"""
from .dbhelper import DatabaseError, query_one


def bib_context(request):
    mySignInUser = request.session.get('signInUser')
    context = {
        'signInUser': mySignInUser,
        'BIB_NAME': 'BIB Assurance',
        'BIB_TAGLINE': 'Trusted Protection for Every Stage of Life',
        'navPendingClaims': 0,
        'navPendingApplications': 0,
        'baseLayout': 'catalog_template/base.html',
    }
    if mySignInUser and mySignInUser.get('role') in ('STAFF', 'ADMIN'):
        context['baseLayout'] = 'catalog_template/backoffice.html'
        try:
            row = query_one("SELECT (SELECT COUNT(*) FROM claim WHERE claim_status = 'Pending') AS claims, "
                            "(SELECT COUNT(*) FROM underwriting_application WHERE app_status = 'Pending') AS apps")
            context['navPendingClaims'] = row['claims'] if row else 0
            context['navPendingApplications'] = row['apps'] if row else 0
        except DatabaseError:
            pass
    return context
