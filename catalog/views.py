"""
Module 2 : Product Catalog & Dynamic Premium Calculator
  - Public pages read the view vw_catalog through sp_get_catalog (Lab 14 callproc)
  - The live calculator calls the MySQL FUNCTION fn_calc_premium (Lab 9.2)
  - A real quote is created by sp_create_quote and stored in premium_quote
  - Admin product / tier / rating-factor management uses the Django ORM,
    exactly like Lab 13 (AddProduct, ProductMain, UpdateProduct)
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from projectweb.dbhelper import (DatabaseError, call_proc, call_proc_one, db_error_message,
                                 query_all, query_one)
from projectweb.filehelper import delete_uploaded, save_image
from projectweb.sessionhelper import role_required

from .models import CoverageTier, PremiumFactor, Product

RISK_ICONS = {1: 'bi-shield-check', 2: 'bi-shield', 3: 'bi-shield-exclamation', 4: 'bi-exclamation-triangle'}
RISK_HINTS = {
    'Personal Accident': {1: 'Office and professional work', 2: 'Light manual work, sales and field visits',
                          3: 'Skilled manual work and regular driving', 4: 'Heavy manual or hazardous work'},
    'default': {1: 'Non-smoker in good health', 2: 'Most applicants',
                3: 'Some medical history or lifestyle factors', 4: 'Significant medical history'},
}


def _thb(value):
    return f'฿{value:,.2f}'


def _customer_age(request):
    mySignInUser = request.session.get('signInUser')
    if mySignInUser and mySignInUser['role'] == 'CUSTOMER':
        row = query_one("SELECT fn_age(date_of_birth, CURDATE()) AS age FROM app_user WHERE user_id = %s",
                        [mySignInUser['user_id']])
        return row['age'] if row else None
    return None


# --------------------------------------------------------------- public pages
def Home(request):
    context = {
        'myProductList': call_proc('sp_get_catalog', [None]),
        'stats': query_one(
            "SELECT (SELECT IFNULL(SUM(approved_amount), 0) FROM claim WHERE claim_status = 'Approved') AS paid_out, "
            "(SELECT COUNT(*) FROM claim WHERE claim_status = 'Approved') AS claims_paid, "
            "(SELECT COUNT(*) FROM policy WHERE policy_status = 'Active') AS active_policies, "
            "(SELECT ROUND(AVG(TIMESTAMPDIFF(HOUR, submitted_at, reviewed_at)), 0) FROM claim "
            " WHERE reviewed_at IS NOT NULL) AS avg_hours"),
    }
    return render(request, 'catalog_template/home.html', context)


def AboutBIB(request):
    return render(request, 'catalog_template/about.html')


def ProductList(request):
    category = request.GET.get('category', '')
    context = {
        'myProductList': call_proc('sp_get_catalog', [category or None]),
        'categories': query_all("SELECT category, COUNT(*) AS n FROM product WHERE is_active = 1 "
                                "GROUP BY category ORDER BY category"),
        'category': category,
    }
    return render(request, 'catalog_template/productlist.html', context)


def ProductDetail(request, productID):
    product = query_one("SELECT * FROM vw_catalog WHERE product_id = %s AND is_active = 1", [productID])
    if product is None:
        messages.error(request, 'This product is not currently available.')
        return redirect('myProductListPage')
    tiers = query_all("SELECT * FROM coverage_tier WHERE product_id = %s ORDER BY tier_level", [productID])
    if not tiers:
        messages.error(request, 'This product is not yet available for purchase.')
        return redirect('myProductListPage')

    # risk levels 1-4 with this product's labels/multipliers (derived table + UNION ALL)
    risks = query_all(
        "SELECT lvl AS risk_level, fn_factor_label(%s, 'RISK', lvl) AS label, "
        "fn_get_multiplier(%s, 'RISK', lvl) AS multiplier "
        "FROM (SELECT 1 AS lvl UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4) AS levels",
        [productID, productID])
    hints = RISK_HINTS.get(product['category'], RISK_HINTS['default'])
    for r in risks:
        r['icon'] = RISK_ICONS[r['risk_level']]
        r['hint'] = hints[r['risk_level']]
    ages = query_all(
        "SELECT range_min, range_max, multiplier, label, product_id FROM premium_factor "
        "WHERE factor_type = 'AGE' AND (product_id = %s OR product_id IS NULL) "
        "ORDER BY range_min, (product_id IS NULL)", [productID])
    seen, age_rows = set(), []
    for a in ages:                      # product overrides win over the global row
        if a['range_min'] not in seen:
            seen.add(a['range_min'])
            age_rows.append(a)

    limits = {}
    for t in tiers:
        step = 100000 if t['min_coverage'] >= 1000000 else (10000 if t['min_coverage'] >= 100000 else 1000)
        limits[str(t['tier_id'])] = {'min': float(t['min_coverage']), 'max': float(t['max_coverage']), 'step': step}

    context = {
        'product': product,
        'tiers': tiers,
        'risks': risks,
        'ageRows': age_rows,
        'tierLimits': limits,
        'customerAge': _customer_age(request),
        'defaultCoverage': tiers[0]['min_coverage'],
    }
    return render(request, 'catalog_template/productdetail.html', context)


def PremiumPreview(request):
    """JSON endpoint for the live calculator. Calls fn_calc_premium in MySQL."""
    try:
        tier_id = int(request.GET.get('tier_id'))
        coverage = Decimal(request.GET.get('coverage'))
        risk = int(request.GET.get('risk_level'))
    except (TypeError, ValueError, InvalidOperation):
        return JsonResponse({'ok': False, 'message': 'Please select a plan, a sum insured and an underwriting class.'})
    age = _customer_age(request)
    if age is None:
        try:
            age = int(request.GET.get('age', 30))
        except ValueError:
            age = 30
    row = query_one(
        "SELECT fn_calc_premium(%s, %s, %s, %s) AS premium, "
        "fn_get_multiplier(t.product_id, 'AGE', %s) AS age_mult, fn_factor_label(t.product_id, 'AGE', %s) AS age_label, "
        "fn_get_multiplier(t.product_id, 'RISK', %s) AS risk_mult, fn_factor_label(t.product_id, 'RISK', %s) AS risk_label, "
        "t.base_annual_premium, t.min_coverage, t.max_coverage, t.duration_months "
        "FROM coverage_tier AS t WHERE t.tier_id = %s",
        [tier_id, age, risk, coverage, age, age, risk, risk, tier_id])
    if row is None:
        return JsonResponse({'ok': False, 'message': 'Please select a plan.'})
    if row['premium'] is None:
        if age < 18:
            msg = 'Applicants must be at least 18 years old.'
        else:
            msg = f"The sum insured for this plan must be between {_thb(row['min_coverage'])} and {_thb(row['max_coverage'])}."
        return JsonResponse({'ok': False, 'message': msg})
    return JsonResponse({
        'ok': True,
        'premium': float(row['premium']),
        'premiumText': _thb(row['premium']),
        'monthlyText': _thb(row['premium'] / 12),
        'coverageText': _thb(coverage),
        'ageLabel': row['age_label'],
        'riskLabel': row['risk_label'],
        'term': f"{row['duration_months']} months",
        'age': age,
    })


@role_required('CUSTOMER')
def CreateQuote(request):
    if request.method != 'POST':
        return redirect('myProductListPage')
    myData = request.POST.copy()
    product_id = myData.get('product_id')
    try:
        myResult = call_proc_one('sp_create_quote', [
            request.session['signInUser']['user_id'],
            int(myData.get('tier_id')), Decimal(myData.get('coverage')), int(myData.get('risk_level'))])
    except (TypeError, ValueError, InvalidOperation):
        messages.error(request, 'Please select a plan, a sum insured and an underwriting class.')
        return redirect('myProductDetailPage', productID=product_id)
    except DatabaseError as e:
        messages.error(request, db_error_message(e))
        return redirect('myProductDetailPage', productID=product_id)
    if myResult['status'] != 'SUCCESS':
        messages.error(request, myResult['message'])
        return redirect('myProductDetailPage', productID=product_id)
    messages.success(request, myResult['message'])
    return redirect('myQuoteDetailPage', quoteID=myResult['quote_id'])


@role_required('CUSTOMER')
def QuoteDetail(request, quoteID):
    quote = query_one("SELECT * FROM vw_quote_details WHERE quote_id = %s AND user_id = %s",
                      [quoteID, request.session['signInUser']['user_id']])
    if quote is None:
        messages.error(request, 'We could not find that quotation.')
        return redirect('myProductListPage')
    quote['base_part'] = (quote['base_annual_premium'] * quote['coverage_amount'] / quote['min_coverage']).quantize(Decimal('0.01'))
    quote['risk_icon'] = RISK_ICONS[quote['risk_level']]
    context = {
        'quote': quote,
        'otherQuotes': query_all("SELECT quote_id, product_name, tier_name, quoted_premium, live_status, created_at "
                                 "FROM vw_quote_details WHERE user_id = %s AND quote_id <> %s "
                                 "ORDER BY created_at DESC LIMIT 5",
                                 [request.session['signInUser']['user_id'], quoteID]),
    }
    return render(request, 'catalog_template/quotedetail.html', context)


# ------------------------------------------------- admin pages (ORM, Lab 13)
@role_required('ADMIN')
def ProductMain(request):
    myProductList = Product.objects.annotate(tier_total=Count('coveragetier')).order_by('product_id')
    sold = {row['product_id']: row['policies_sold'] for row in query_all("SELECT product_id, policies_sold FROM vw_catalog")}
    for p in myProductList:
        p.policies_sold = sold.get(p.product_id, 0)
    context = {'myProductList': myProductList}
    return render(request, 'catalog_template/productmain.html', context)


def _product_form_errors(myData):
    required = ('product_code', 'product_name', 'tagline', 'description', 'category')
    if any(myData.get(k, '').strip() == '' for k in required):
        return 'Please complete all required fields.'
    return None


@role_required('ADMIN')
def AddProduct(request):
    context = {'categories': [c[0] for c in Product.CATEGORY_CHOICES]}
    if request.method == 'POST':
        myData = request.POST.copy()
        context['form'] = myData
        error = _product_form_errors(myData)
        if error:
            context['returnMessage'] = error
            return render(request, 'catalog_template/addproduct.html', context)

        newProductRecord = Product()   # สร้าง Record ใหม่ (Lab 13)
        newProductRecord.product_code = myData.get('product_code').strip().upper()
        newProductRecord.product_name = myData.get('product_name').strip()
        newProductRecord.tagline = myData.get('tagline').strip()
        newProductRecord.description = myData.get('description').strip()
        newProductRecord.category = myData.get('category')
        newProductRecord.requires_beneficiary = 'requires_beneficiary' in myData
        newProductRecord.is_active = True
        newProductRecord.created_at = timezone.now()
        if 'productimage' in request.FILES:   # LabExtra
            path, err = save_image(request.FILES['productimage'], 'product', allow_svg=True)
            if err:
                context['returnMessage'] = err
                return render(request, 'catalog_template/addproduct.html', context)
            newProductRecord.thumbnail_path = path
        try:
            newProductRecord.save()   # บันทึกการเพิ่มข้อมูลลงใน Database
        except (IntegrityError, DatabaseError) as e:
            delete_uploaded(newProductRecord.thumbnail_path)
            context['returnMessage'] = db_error_message(e)
            return render(request, 'catalog_template/addproduct.html', context)
        messages.success(request, f'{newProductRecord.product_name} has been created. Please add at least one plan.')
        return redirect('myManageTiersPage', productID=newProductRecord.product_id)
    return render(request, 'catalog_template/addproduct.html', context)


@role_required('ADMIN')
def UpdateProduct(request, productID):
    context = {'categories': [c[0] for c in Product.CATEGORY_CHOICES]}
    theProduct = Product.objects.get(product_id=productID)
    context['theProduct'] = theProduct

    if request.method == 'POST':
        myData = request.POST.copy()
        if 'save' in myData:
            error = _product_form_errors(myData)
            if error:
                messages.error(request, error)
                return redirect('myUpdateProductPage', productID=productID)
            myUpdatedProduct = Product.objects.get(product_id=theProduct.product_id)
            myUpdatedProduct.product_code = myData.get('product_code').strip().upper()
            myUpdatedProduct.product_name = myData.get('product_name').strip()
            myUpdatedProduct.tagline = myData.get('tagline').strip()
            myUpdatedProduct.description = myData.get('description').strip()
            myUpdatedProduct.category = myData.get('category')
            myUpdatedProduct.requires_beneficiary = 'requires_beneficiary' in myData
            myUpdatedProduct.is_active = 'is_active' in myData
            old_path = None
            if 'productimage' in request.FILES:
                path, err = save_image(request.FILES['productimage'], 'product', allow_svg=True)
                if err:
                    messages.error(request, err)
                    return redirect('myUpdateProductPage', productID=productID)
                old_path, myUpdatedProduct.thumbnail_path = myUpdatedProduct.thumbnail_path, path
            try:
                myUpdatedProduct.save()
            except (IntegrityError, DatabaseError) as e:
                messages.error(request, db_error_message(e))
                return redirect('myUpdateProductPage', productID=productID)
            delete_uploaded(old_path)
            messages.success(request, 'Product details have been updated.')
            return redirect('myProductMainPage')
        elif 'delete' in myData:
            myDeletedProduct = Product.objects.get(product_id=theProduct.product_id)
            try:
                myDeletedProduct.delete()
            except (IntegrityError, DatabaseError):
                messages.error(request, 'Policies have already been issued under this product, so it cannot be '
                                        'deleted. Mark it as inactive to remove it from the catalogue.')
                return redirect('myUpdateProductPage', productID=productID)
            delete_uploaded(theProduct.thumbnail_path)
            messages.success(request, 'The product has been deleted.')
            return redirect('myProductMainPage')
        elif 'nochange' in myData:
            return redirect('myProductMainPage')

    return render(request, 'catalog_template/updateproduct.html', context)


def _tier_from_post(tier, myData):
    tier.tier_name = myData.get('tier_name', '').strip()
    tier.tier_level = int(myData.get('tier_level'))
    tier.min_coverage = Decimal(myData.get('min_coverage'))
    tier.max_coverage = Decimal(myData.get('max_coverage'))
    tier.base_annual_premium = Decimal(myData.get('base_annual_premium'))
    tier.deductible = Decimal(myData.get('deductible') or '0')
    tier.duration_months = int(myData.get('duration_months'))
    tier.perks = myData.get('perks', '').strip() or None
    return tier


@role_required('ADMIN')
def ManageTiers(request, productID):
    theProduct = Product.objects.get(product_id=productID)
    if request.method == 'POST':
        myData = request.POST.copy()
        newTier = CoverageTier(product=theProduct)
        try:
            _tier_from_post(newTier, myData)
            if not newTier.tier_name:
                raise ValueError
            newTier.save()
            messages.success(request, f'The {newTier.tier_name} plan has been added.')
        except (ValueError, InvalidOperation, TypeError):
            messages.error(request, 'Please complete every plan field with valid amounts.')
        except (IntegrityError, DatabaseError) as e:    # CHECK constraints -> friendly text
            messages.error(request, db_error_message(e))
        return redirect('myManageTiersPage', productID=productID)
    context = {
        'theProduct': theProduct,
        'myTierList': CoverageTier.objects.filter(product=theProduct).order_by('tier_level'),
        'nextLevel': (CoverageTier.objects.filter(product=theProduct).count() + 1),
    }
    return render(request, 'catalog_template/managetiers.html', context)


@role_required('ADMIN')
def UpdateTier(request, tierID):
    theTier = CoverageTier.objects.get(tier_id=tierID)
    if request.method == 'POST':
        myData = request.POST.copy()
        if 'save' in myData:
            try:
                _tier_from_post(theTier, myData)
                theTier.save()
                messages.success(request, 'The plan has been updated. New quotations will use the revised rates.')
                return redirect('myManageTiersPage', productID=theTier.product_id)
            except (ValueError, InvalidOperation, TypeError):
                messages.error(request, 'Please enter valid amounts.')
            except (IntegrityError, DatabaseError) as e:
                messages.error(request, db_error_message(e))
            return redirect('myUpdateTierPage', tierID=tierID)
        elif 'delete' in myData:
            try:
                theTier.delete()
                messages.success(request, 'The plan has been deleted.')
            except (IntegrityError, DatabaseError):
                messages.error(request, 'Policies have already been issued under this plan, so it cannot be deleted.')
                return redirect('myUpdateTierPage', tierID=tierID)
            return redirect('myManageTiersPage', productID=theTier.product_id)
        return redirect('myManageTiersPage', productID=theTier.product_id)
    return render(request, 'catalog_template/updatetier.html', {'theTier': theTier})


@role_required('ADMIN')
def ManageFactors(request):
    if request.method == 'POST':
        myData = request.POST.copy()
        try:
            if 'save' in myData:
                f = PremiumFactor.objects.get(factor_id=int(myData.get('factor_id')))
                f.multiplier = Decimal(myData.get('multiplier'))
                f.label = myData.get('label', '').strip() or f.label
                f.save()
                messages.success(request, 'The rating factor has been updated.')
            elif 'add' in myData:
                f = PremiumFactor(
                    product=Product.objects.get(product_id=int(myData['product_id'])) if myData.get('product_id') else None,
                    factor_type=myData.get('factor_type'),
                    range_min=int(myData.get('range_min')), range_max=int(myData.get('range_max')),
                    multiplier=Decimal(myData.get('multiplier')), label=myData.get('label', '').strip() or 'Custom')
                f.save()
                messages.success(request, 'The rating factor has been added.')
            elif 'delete' in myData:
                PremiumFactor.objects.filter(factor_id=int(myData.get('factor_id'))).delete()
                messages.success(request, 'The rating factor has been removed.')
        except (ValueError, InvalidOperation, TypeError, Product.DoesNotExist):
            messages.error(request, 'Please enter valid amounts.')
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, db_error_message(e))
        return redirect('myManageFactorsPage')
    context = {
        'factors': PremiumFactor.objects.select_related('product').order_by('factor_type', 'product_id', 'range_min'),
        'products': Product.objects.order_by('product_name'),
    }
    return render(request, 'catalog_template/managefactors.html', context)
