﻿"""
Definition of views.
"""
from django.http import JsonResponse
from django.shortcuts import render, redirect, render_to_response
from django.template.context_processors import csrf
from django.core.urlresolvers import reverse
from django.http import HttpRequest, HttpResponseRedirect
from django.template import RequestContext
from django.views.generic.base import TemplateView
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q
import seeker
import json
import urllib
from datetime import datetime, time
import FMI.settings
import app.elastic as elastic
import app.scrape_ds as scrape_ds
import app.excitometer as excitometer
import app.sentiment as sentiment
import app.product as product
import app.market as market
import app.load as load
import app.crawl as crawl
import app.survey as survey
import app.guide as guide
import app.facts as facts
import app.r_and_d as r_and_d
import app.fmi_admin as fmi_admin
import app.azure as azure
import app.wb_excel as wb_excel
import app.models as models
import app.survey
from .forms import *


models.SurveySeekerView.decoder = survey.seekerview_answer_value_decode

def home(request):
    """Renders the home page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/index.html',
        context_instance = RequestContext(request,
        {
            'title':'Home Page',
            'year':datetime.now().year,
        })
    )


def product_insight_view(request):
    """Renders the product_insight page."""
    if request.method == 'POST':
        if 'search_pi' in request.POST:
            return redirect('search_pi')

    return render(request, 'app/product_insight.html',
                  context_instance = RequestContext(request, {'message':'IFF - Insight Platform', 'year':datetime.now().year,} ))

def r_and_d_view(request):
    """Renders the R&D page."""
    if request.method == 'POST':
        form = r_and_d_form(request.POST)
        if form.is_valid():
            ipc_field = '00000000' + form.cleaned_data['ipc_field']
            ipc_field = ipc_field[-6:]
            molecule_d = r_and_d.molecules(ipc_field)
            if molecule_d:
                models.molecules_d[ipc_field] = molecule_d
                return render(request, 'app/r_and_dresults.html', {'molecules_d' : models.molecules_d } )
            else:
                form.add_form_error("Molecule properties and/or image could not be read from R&D")
    else:
        form = r_and_d_form(initial={'ipc_field':'100154'})

    return render(request, 'app/r_and_d.html', {'form': form },
                  context_instance = RequestContext(request, {'message':'IFF - Insight Platform', 'year':datetime.now().year,} ))

def patents(request):
    """Renders the Patents page."""
    # prepare search_excel with the right
    #models.ExcelDoc = seeker.mapping.document_from_model(models.patents, index="excel_patents", using=models.client)
    #seeker.register(models.ExcelDoc)
    workbook_name = 'patents'

    workbook = wb_excel.workbooks[workbook_name]
    es_index = workbook['es_index']
    models.ExcelDoc = seeker.mapping.document_from_index(es_index, using=models.client)
    models.ExcelSeekerView.document = models.ExcelDoc
    models.ExcelSeekerView.index = es_index['index']
    models.ExcelSeekerView.facets = es_index['facets']
    models.ExcelSeekerView.facets_keyword = es_index['facets_keyword']
    models.ExcelSeekerView.display = es_index['display']
    models.ExcelSeekerView.summary = es_index['summary']
    models.ExcelSeekerView.sumheader = es_index['sumheader']
    models.ExcelSeekerView.SUMMARY_URL = es_index['SUMMARY_URL']
    models.ExcelSeekerView.urlfields = es_index['urlfields']
    models.ExcelSeekerView.tabs = es_index['tabs']
    models.ExcelSeekerView.workbooks = wb_excel.workbooks

    kwargs={}
    kwargs['workbook_name'] = workbook_name
    kwargs['storyboard_name'] = 'initial'
    kwargs['dashboard_name'] = 'initial'
    url = reverse('search_excel')
    params = urllib.parse.urlencode(kwargs)
    #return redirect('search_excel')
    return HttpResponseRedirect(url + "?%s" % params)


#def ingr_molecules(request):
    #workbook_name = 'ingr_molecules'
def search_workbook(request):
    # prepare search_excel with the right
    #models.ExcelDoc2 = seeker.mapping.document_from_model(models.ingr_molecules, index="excel_ingr_molecules", using=models.client)
    #seeker.register(models.ExcelDoc)
    workbook_name = request.GET.get('workbook_name', '').strip()
    storyboard_name = request.GET.get('storyboard_name', 'initial').strip()
    dashboard_name = request.GET.get('dashboard_name', 'initial').strip()

    workbook = wb_excel.workbooks[workbook_name]
    es_index = workbook['es_index']
    models.ExcelDoc = seeker.mapping.document_from_index(es_index, using=models.client)
    models.ExcelSeekerView.document = models.ExcelDoc
    models.ExcelSeekerView.index = es_index['index']
    models.ExcelSeekerView.facets = es_index['facets']
    models.ExcelSeekerView.facets_keyword = es_index['facets_keyword']
    models.ExcelSeekerView.display = es_index['display']
    models.ExcelSeekerView.summary = es_index['summary']
    models.ExcelSeekerView.sumheader = es_index['sumheader']
    models.ExcelSeekerView.SUMMARY_URL = es_index['SUMMARY_URL']
    models.ExcelSeekerView.urlfields = es_index['urlfields']
    models.ExcelSeekerView.tabs = es_index['tabs']
    models.ExcelSeekerView.workbooks = wb_excel.workbooks

    kwargs={}
    kwargs['workbook_name'] = workbook_name
    kwargs['storyboard_name'] = storyboard_name
    kwargs['dashboard_name'] = dashboard_name
    url = reverse('search_excel')
    params = urllib.parse.urlencode(kwargs)

    #return redirect('search_excel')
    # return HttpResponseRedirect(url + "?%s" % params,  content_type='application/json')
    
    return HttpResponseRedirect(url + "?%s" % params)


def excitometer_view(request):
    """Renders the Excitometer page."""
    correlation_li = []
    chart_data = []
    facets_data = {}
    tiles_d = {}
    tiles_select = {}

    if request.method == 'POST':
        form = excitometer_form(request.POST)
        if form.is_valid():
            IPC_field = form.cleaned_data['IPC_field']
            correlations_field = form.cleaned_data['correlations_field']
            FITTE_norm_field = form.cleaned_data['FITTE_norm_field']
            CIU_field = form.cleaned_data['CIU_field']
            regions_field = form.cleaned_data['regions_field']
            type_field = form.cleaned_data['type_field']
            regulator_field = form.cleaned_data['regulator_field']
            if 'uptake' in form.data:
                correlation_li = excitometer.correlate(IPC_field, correlations_field, FITTE_norm_field, CIU_field, regions_field, type_field, regulator_field)
                tiles_d = excitometer.uptake(correlations_field)
                if correlation_li is None or tiles_d is None:
                    form.add_form_error("Uptake failed, first retrieve ingr molecules data")
            if 'retrieve_ingredients' in form.data:
                if excitometer.retrieve_ingredients() == False:
                    form.add_form_error("Failed to read the correlation master data file")
            #return render(request, 'app/excitometer.html', {'form': form, 'correlation_li' : correlation_li, 'chart_data' : chart_data } )
    else:
        form = excitometer_form(initial={'type_field':['Vanilla'],'regulator_field':['Nat']})
 
    context = {
        'message':'IFF - Insight Platform',
        'year':datetime.now().year,
        'form': form,
        'correlation_li' : correlation_li,
        'chart_data' : chart_data,
        'facets_data': json.dumps(facets_data),
        'tiles_select': json.dumps(tiles_select),
        'tiles_d': json.dumps(tiles_d),
        'storyboard' : json.dumps(excitometer.storyboard),
        'dashboard_name' : 'Uptake',
        'dashboard': json.dumps(excitometer.dashboard),
        }

    return render(request, 'app/excitometer.html', context)

def scent_emotion_view(request):
    """Renders the scent emotion page."""
    if request.method == 'POST':
        if 'search_scentemotion' in request.POST:
            return redirect('search_scentemotion')
        elif 'search_studies' in request.POST:
            return redirect('search_studies')

    return render(request, 'app/scent_emotion.html',
                  context_instance = RequestContext(request, {'message':'IFF - Insight Platform', 'year':datetime.now().year,} ))

def scrape_view(request):
    """Renders the scrape page."""
    if request.method == 'POST':
        form = scrape_form(request.POST)
        if form.is_valid():
            site_choices = form.cleaned_data['site_choices_field']
            scrape_choices = form.cleaned_data['scrape_choices_field']
            brand_field = form.cleaned_data['brand_field']
            if 'scrape' in form.data:
                models.scrape_li = scrape_ds.scrape_ds(site_choices, scrape_choices, brand_field)
                if not product.scrape_save(brand_field):
                    form.add_form_error("Could not save scrape results")
            if 'retrieve' in form.data:
                if not product.scrape_retrieve(brand_field):
                    form.add_form_error("Could not retrieve scrape results")
            if len(models.scrape_li) == 0:
                form.add_form_error("First retrieve or scrape the web for this brand")
            else:
                if 'explore' in form.data:
                    return render(request, 'app/scraperesults.html', {'brand': brand_field, 'scrape_li' : models.scrape_li } )
                if 'sentiment' in form.data:
                    sentiment.sentiment(brand_field)
                    if not product.scrape_save(brand_field):
                        form.add_form_error("Could not save scrape results")
                    return render(request, 'app/scraperesults.html', {'brand': brand_field, 'scrape_li' : models.scrape_li } )
            return render(request, 'app/scrape.html', {'form': form, 'scrape_li' : models.scrape_li } )
    else:
        form = scrape_form(initial={'site_choices_field':['fragrantica'],'scrape_choices_field':['accords','moods','notes']})

    return render(request, 'app/scrape.html', {'form': form },
                  context_instance = RequestContext(request, {'message':'IFF - Insight Platform', 'year':datetime.now().year,} ))

def market_insight_view(request):
    "Renders the market insight page."
    if request.method == 'POST':
        if 'search_mi' in request.POST:
            return redirect('search_mi')
        elif 'search_feedly' in request.POST:
            return redirect('search_feedly')
        elif 'search_si_sites' in request.POST:
            return redirect('search_si_sites')
        elif 'search_excel' in request.POST:
            # prepare search_excel with the right
            #models.ExcelDoc = seeker.mapping.document_from_model(models.ecosystem, index="excel_ecosystem", using=models.client)
            #seeker.register(models.ExcelDoc)
            workbook_name = 'ecosystem'

            workbook = wb_excel.workbooks[workbook_name]
            es_index = workbook['es_index']
            models.ExcelDoc = seeker.mapping.document_from_index(es_index, using=models.client)
            models.ExcelSeekerView.document = models.ExcelDoc
            models.ExcelSeekerView.index = es_index['index']
            models.ExcelSeekerView.facets = es_index['facets']
            models.ExcelSeekerView.facets_keyword = es_index['facets_keyword']
            models.ExcelSeekerView.display = es_index['display']
            models.ExcelSeekerView.summary = es_index['summary']
            models.ExcelSeekerView.sumheader = es_index['sumheader']
            models.ExcelSeekerView.SUMMARY_URL = es_index['SUMMARY_URL']
            models.ExcelSeekerView.urlfields = es_index['urlfields']
            models.ExcelSeekerView.tabs = es_index['tabs']
            models.ExcelSeekerView.workbooks = wb_excel.workbooks

            kwargs={}
            kwargs['workbook_name'] = workbook_name
            kwargs['storyboard_name'] = 'initial'
            kwargs['dashboard_name'] = 'initial'
            url = reverse('search_excel')
            params = urllib.parse.urlencode(kwargs)
            #return redirect('search_excel')
            return HttpResponseRedirect(url + "?%s" % params)
    return render(request, 'app/market_insight.html', 
                  context_instance = RequestContext(request,
                                                    {'es_hosts' : FMI.settings.ES_HOSTS, 'message':'IFF - Insight Platform', 'year':datetime.now().year,} ))

def guide_view(request):
    """Renders the guide page."""
    route_name = ''
    step_name = ''
    site_name = ''
    menu_name = ''
    view_name = ''
    benchmark = ''
    results = {}
    tiles_d = {}
    facets = {}
    if request.method == 'GET':
        route_name = request.GET.get('route_select', '')
        site_name = request.GET.get('site_select', '')
        if route_name != '':
            step_name = request.GET.get('step_name', '')
            route_steps = guide.routes[route_name][1]
            step_ix = 0
            # new route selected, start with the first step of this route
            if not ('guide_previous' in request.GET or 'guide_next' in request.GET):
                step_name = route_steps[0]
            else:
                for step in route_steps:
                    if step == step_name:
                        break
                    else:
                        step_ix = step_ix + 1
                if 'guide_previous' in request.GET:
                    if step_ix > 0:
                        step_name = route_steps[step_ix - 1]
                    else:
                        step_name = route_steps[0]
                if 'guide_next' in request.GET:
                    if step_ix < len(route_steps)-1:
                        step_name = route_steps[step_ix + 1]
            if step_ix < len(route_steps)-1:
                results, facets = guide.route_step(request, route_name, step_name)
            else:      
                # destination reached, determine step_name                     
                step_name = guide.route_dest(request, route_name, step_name)
        else:
            if site_name != '':
                menu_name = request.GET.get('menu_name', '')
                view_name = request.GET.get('view_name', '')
                benchmark = request.GET.get('benchmark', '')
                tile_facet_field = request.GET.get('tile_facet_field', '')
                if site_name != '':
                    results, facets = guide.site_menu(request, site_name, menu_name, view_name, tile_facet_field)


    context = {
            'insight_api' : FMI.settings.INSIGHT_API['url'],
            'facets'    : facets,
            'results'   : results,
            'site_name' : site_name,
            'menu_name' : menu_name,
            'view_name' : view_name,
            'benchmark' : benchmark,
            'sites'     : json.dumps(guide.sites),
            'site_views': json.dumps(guide.site_views)
        }

    return render(request, 'app/guide.html', context )


def facts_view(request):
    """Renders the facts page."""
    if request.method == 'POST':
        form = facts_form(request.POST)
        if form.is_valid():
            facts_choices = form.cleaned_data['facts_choices_field']
            norms_choices = form.cleaned_data['norms_choices_field']
            survey_field = form.cleaned_data['survey_field']
            facts_d = facts.facts_survey(survey_field, facts_choices, norms_choices)
            load.load_studies_facts(survey_field, facts_d)
            return render(request, 'app/factsresults.html', {'facts_d' : facts_d } )
    else:
        form = facts_form(initial={'facts_choices_field':['emotions'],'norms_choices_field':['age']})

    return render(request, 'app/facts.html', {'form': form },
                  context_instance = RequestContext(request, {'message':'IFF - Insight Platform', 'year':datetime.now().year,} ))

def consumer_insight_view(request):
    "Renders the consumer_insight page."
    if request.method == 'POST':
        if 'search_mi' in request.POST:
            return redirect('search_mi')
        elif 'search_feedly' in request.POST:
            return redirect('search_feedly')
        elif 'search_si_sites' in request.POST:
            return redirect('search_si_sites')
        elif 'search_pi' in request.POST:
            return redirect('search_pi')
        elif 'search_scentemotion' in request.POST:
            return redirect('search_scentemotion')
        elif 'search_survey' in request.POST:
            #return redirect('search_survey?tab=#storyboard_tab')
            #return redirect('search_survey', tab='#storyboard_tab')
            #return redirect('search_survey')
            #seekerview = models.SurveySeekerView()
            #request.method = 'GET'
            #request.path = '/search_survey'
            #request.path_info = '/search_survey'
            #seekerview.request = request
            #return seekerview.render()
            #url = reverse('search_survey', args=(), kwargs={'survey.keyword': '2015'})
            kwargs={}
            if 'workbook_name' in request.POST:
                kwargs['workbook_name'] = request.POST['workbook_name']
            if 'dashboard_name' in request.POST:
                kwargs['dashboard_name'] = request.POST['dashboard_name']
            url = reverse('search_survey')
            params = urllib.parse.urlencode(kwargs)
            return HttpResponseRedirect(url + "?%s" % params)
        elif 'search_studies' in request.POST:
            return redirect('search_studies')

    return render(request, 'app/consumer_insight.html', 
                  context_instance = RequestContext(request,
                                                    {'es_hosts' : FMI.settings.ES_HOSTS, 'message':'IFF - Insight Platform', 'year':datetime.now().year,} ))


def platform_admin_view(request):
    "Renders the platform admin page."
    if request.method == 'POST':
        if 'scrape' in request.POST:
            return redirect('scrape')
        elif 'elastic' in request.POST:
            return redirect('product_elastic')
    return render(request, 'app/platform_admin.html', 
                  context_instance = RequestContext(request,
                                                    {'es_hosts' : FMI.settings.ES_HOSTS, 'message':'IFF - Insight Platform', 'year':datetime.now().year,} ))

def crawl_view(request):
    """Renders the crawl page."""
    if request.method == 'POST':
        form = crawl_form(request.POST)
        form.is_valid()
        # called from crawh.html
        if form.is_valid():
            from_date = form.cleaned_data['from_date']
            nrpages = form.cleaned_data['nrpages_field']
            site_choices = form.cleaned_data['site_choices_field']
            scrape_choices = form.cleaned_data['scrape_choices_field']
            rss_field = form.cleaned_data['rss_field']
            product_field = form.cleaned_data['product_field']
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            if from_date == None:
                today = datetime.now()
                from_date = datetime(today.year-1, 1, 1, 0, 0, 0)
            if 'crawl_si_sites' in form.data:
                for site_choice in site_choices:
                    if site_choice == 'apf':
                        crawl.crawl_apf(scrape_choices, nrpages)
                    elif site_choice == 'cosmetics':
                        crawl.crawl_cosmetic(scrape_choices, nrpages)
                    else:
                        crawl.si_site(site_choice, nrpages)
            elif 'crawl_mi' in form.data:
                if not market.index_posts(from_date, username, password):
                    form.add_form_error("Could not index category posts")
            if 'crawl_pi' in form.data:
                if product_field == '':
                    form.add_form_error("Specify a product")
                else:
                    if not product.crawl_product(index_choices, product_field):
                        form.add_form_error("Could not save product data")
            if 'index_pi' in form.data:
                if product_field == '':
                    form.add_form_error("Specify a product")
                else:
                    if not product.index_product(index_choices, product_field):
                        form.add_form_error("Could not retrieve product data")
            if 'crawl_feedly' in form.data:
                if not crawl.crawl_feedly(from_date, rss_field):
                     form.add_form_error("Could not retrieve feedly data, expired")
            if 'return_survey' in form.data:
                pass
            return render(request, 'app/crawl.html', {'form': form, 'es_hosts' : FMI.settings.ES_HOSTS, 'scrape_li' : models.scrape_li } )
    else:
        form = crawl_form(initial={'scrape_choices_field':['product', 'blog'], 'excel_choices_field':['recreate']})

    return render(request, 'app/crawl.html', {'form': form, 'es_hosts' : FMI.settings.ES_HOSTS },
                  context_instance = RequestContext(request, {'message':'IFF - Insight Platform', 'year':datetime.now().year,} ))


def load_view(request):
    """Renders the load page."""
    if request.method == 'POST':
        form = load_form(request.POST)
        form.is_valid()
        ci_filename = form.cleaned_data['ci_filename_field']
        cimap_filename = form.cleaned_data['cimap_filename_field']
        # called form loadresults.html
        if 'load_survey' in form.data:
            load.load_survey(request, ci_filename, cimap_filename)
        # called from load.html
        if form.is_valid():
            cft_filename = form.cleaned_data['cft_filename_field']
            excel_choices = form.cleaned_data['excel_choices_field']
            excel_filename = form.cleaned_data['excel_filename_field']
            indexname = form.cleaned_data['indexname_field']
            ci_filename = form.cleaned_data['ci_filename_field']
            cimap_filename = form.cleaned_data['cimap_filename_field']
            if 'load_scentemotion' in form.data:
                load.load_scentemotion(cft_filename)
            if 'load_excel' in form.data:
                if not load.load_excel(excel_filename, excel_choices, indexname):
                    form.add_form_error("Could not retrieve or index excel file")
            if 'map_survey' in form.data:
                field_map, col_map, header_map = load.map_survey(ci_filename, cimap_filename)
                qa = {}
                for question, answers in survey.qa.items():
                    qa[question] = list(answers.keys())
                context = {
                    'form'          : form,
                    'col_map'       : col_map,
                    'header_map'    : header_map,
                    'qa'            : qa,
                    }
                return render(request, 'app/loadresults.html', context )
            if 'return_survey' in form.data:
                pass
            return render(request, 'app/load.html', {'form': form, 'es_hosts' : FMI.settings.ES_HOSTS } )
    else:
        form = load_form(initial={'excel_choices_field':['recreate']})

    return render(request, 'app/load.html', {'form': form, 'es_hosts' : FMI.settings.ES_HOSTS },
                  context_instance = RequestContext(request, {'message':'IFF - Insight Platform', 'year':datetime.now().year,} ))

def fmi_admin_view(request):
    """Renders the Admin Index page."""
    if request.method == 'POST':
        form = fmi_admin_form(request.POST)
        if form.is_valid():
            index_choices = form.cleaned_data['index_choices_field']
            excel_filename = form.cleaned_data['excel_filename_field']
            opml_filename = form.cleaned_data['opml_filename_field']
            keyword_filename = form.cleaned_data['keyword_filename_field']
            if 'index_elastic' in form.data:
                fmi_admin.create_index_elastic(index_choices, excel_filename)
            elif 'analyzer' in form.data:
                fmi_admin.create_analyzer(index_choices)
            if 'index_azure' in form.data:
                azure.create_index_azure(index_choices)
            elif 'export_opml' in form.data:
                if not fmi_admin.export_opml(index_choices, opml_filename):
                    form.add_form_error("Could not export OPML")
            elif 'import_opml' in form.data:
                if not fmi_admin.import_opml(index_choices, opml_filename):
                    form.add_form_error("Could not import OPML")
            elif 'keywords' in form.data:
                if not fmi_admin.read_keywords(index_choices, keyword_filename):
                    form.add_form_error("Could not read keywords file")
            return render(request, 'app/fmi_admin.html', {'form': form })
    else:
        form = fmi_admin_form(initial={'index_choices_field':['cosmetic']})

    return render(request, 'app/fmi_admin.html', {'form': form },
                  context_instance = RequestContext(request, {'message':'IFF - Insight Platform', 'year':datetime.now().year,} ))

def elastic_view(request):
    """Renders the elastic page."""
    assert isinstance(request, HttpRequest)
    elastic.elastic_bank()
#    elastic.elastic_seeker1()
    elastic.elastic_seeker2()
    elastic.elastic_review()
    elastic.sharepoint_mi()
    return render(
        request,
        'app/index.html',
        context_instance = RequestContext(request,
        {
            'title':'Home Page',
            'year':datetime.now().year,
        })
    )


def autocomplete_view(request):
    query = request.GET.get('term', '')
#    resp = models.client.suggest(
#        index='review',
#        body={                                                                                                                                          
#            'perfume': {
#               "text": query,
#               "completion": {
#                   "field": 'perfume',
#               }
#            }
#        }
#    )
    s = Search(using=models.client, index = "review")
    s = s.filter("term", perfume=query)
    resp = s.execute()

    perfumes = []
    for hit in resp:
        perfumes.append(hit.perfume)
    data = json.dumps(perfumes)
    mimetype = 'application/json'
    return HttpResponse(data, mimetype)

def contact(request):
    """Renders the contact page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/contact.html',
        context_instance = RequestContext(request,
        {
            'title':'Contact',
            'message':'Your contact page.',
            'year':datetime.now().year,
        })
    )

def about(request):
    """Renders the about page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/about.html',
        context_instance = RequestContext(request,
        {
            'title':'About',
            'message':'Your application description page.',
            'year':datetime.now().year,
        })
    )

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('/accounts/register_complete')

    else:
        form = RegistrationForm()
    token = {}
    token.update(csrf(request))
    token['form'] = form

    return render_to_response('registration/register.html', token)

def registrer_complete(request):
    return render_to_response('registration/registrer_complete.html')