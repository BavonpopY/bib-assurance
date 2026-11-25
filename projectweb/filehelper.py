"""
Image uploads, LabExtra style (myshop/views.py AddProduct):

    fileImage = request.FILES['productimage']
    fileImageName = fileImage.name.replace(' ', '')
    fs = FileSystemStorage(location='media/product')
    myFileName = fs.save(fileImageName, fileImage)

Same idea here, with three folders exactly like myfirstweb/media/product:
    media/product/   product images            (product.thumbnail_path)
    media/avatar/    profile pictures          (app_user.avatar_path)
    media/claim/     claim supporting documents (claim_evidence.image_path)
    media/application/ ID cards, proof of occupation (application_document.image_path)

Differences on purpose:
  * the location is built from settings.MEDIA_ROOT, so it works whichever
    folder runserver is started from;
  * only real images are accepted (Pillow opens and verifies them);
  * an 8-character random prefix stops two customers overwriting "scan.jpg";
  * the value returned (and stored in MySQL) is the path relative to
    MEDIA_ROOT, e.g. "claim/3f9a1c2e_invoice.jpg"; templates show it with
    {{ MEDIA_URL }}{{ path }}.
"""
import os
import re
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from PIL import Image

RASTER_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
UPLOAD_NAME = re.compile(r'^[0-9a-f]{8}_')


def save_image(uploaded_file, subfolder, allow_svg=False):
    """Save an uploaded image in MEDIA_ROOT/<subfolder>.
    Returns (relative_path, None) or (None, error_message)."""
    if uploaded_file is None:
        return None, 'No file was uploaded.'
    fileImageName = os.path.basename(uploaded_file.name).replace(' ', '')
    fileImageName = re.sub(r'[^A-Za-z0-9._-]', '', fileImageName) or 'image'
    ext = os.path.splitext(fileImageName)[1].lower()

    if uploaded_file.size > settings.BIB_MAX_UPLOAD_MB * 1024 * 1024:
        return None, f'Files must be {settings.BIB_MAX_UPLOAD_MB} MB or smaller.'

    if ext == '.svg' and allow_svg:
        content = uploaded_file.read().decode('utf-8', 'ignore').lower()
        uploaded_file.seek(0)
        if '<svg' not in content or '<script' in content or 'javascript:' in content \
                or re.search(r'\son\w+\s*=', content):
            return None, 'This SVG file cannot be accepted.'
    elif ext in RASTER_EXT:
        try:
            Image.open(uploaded_file).verify()
        except Exception:
            return None, f'"{uploaded_file.name}" is not a valid image file.'
        uploaded_file.seek(0)
    else:
        allowed = 'JPG, PNG, WEBP or GIF' + (' or SVG' if allow_svg else '')
        return None, f'Please upload a {allowed} image.'

    fs = FileSystemStorage(location=settings.MEDIA_ROOT / subfolder)
    myFileName = fs.save(f'{uuid.uuid4().hex[:8]}_{fileImageName}', uploaded_file)
    return f'{subfolder}/{myFileName}', None


def delete_uploaded(relative_path):
    """Delete a file that was uploaded through save_image().
    Seeded files (no random prefix) are never deleted."""
    if not relative_path or not UPLOAD_NAME.match(os.path.basename(relative_path)):
        return
    full = (settings.MEDIA_ROOT / relative_path).resolve()
    if str(full).startswith(str(settings.MEDIA_ROOT.resolve())) and full.is_file():
        try:
            full.unlink()
        except OSError:
            pass
