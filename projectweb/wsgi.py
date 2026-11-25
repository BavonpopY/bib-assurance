"""
WSGI config for projectweb project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectweb.settings')

application = get_wsgi_application()
