from django.conf.urls import patterns, include, url
from django.contrib.staticfiles.urls import staticfiles_urlpatterns, static
from django.http import HttpResponse

from FuzzEd.models import Job
from FuzzEd import settings

from django.contrib import admin

import api_oauth

admin.autodiscover()

re_uuid = "[0-F]{8}-[0-F]{4}-[0-F]{4}-[0-F]{4}-[0-F]{12}"

urlpatterns = patterns('',
    # admin
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),

    # web page
    url(r'^$', 'FuzzEd.views.index', name='index'),
    url(r'^login/$', 'FuzzEd.views.login', name='login'),
    url(r'^about/$', 'FuzzEd.views.about', name='about'),    
    url(r'^settings/$', 'FuzzEd.views.settings', name='settings'),    
    
    url(r'^graphs/(?P<graph_id>\d+)/$', 'FuzzEd.views.dashboard_edit', name='dashboard_edit'),
    url(r'^editor/(?P<graph_id>\d+)$', 'FuzzEd.views.editor', name='editor'),
    url(r'^snapshot/(?P<graph_id>\d+)$', 'FuzzEd.views.snapshot', name='snapshot'),
        
    url(r'^projects/$', 'FuzzEd.views.projects', name='projects'),
    url(r'^projects/new/$', 'FuzzEd.views.project_new', name='project_new'),
    url(r'^projects/(?P<project_id>\d+)/$', 'FuzzEd.views.project_edit', name='project_edit'),
    url(r'^projects/(?P<project_id>\d+)/dashboard/$', 'FuzzEd.views.dashboard', name='dashboard'),
    url(r'^projects/(?P<project_id>\d+)/dashboard/new/(?P<kind>\w{1,50})$', 'FuzzEd.views.dashboard_new', name='dashboard_new'),
    
    url(r'^robots\.txt$', lambda r: HttpResponse("User-agent: *\nDisallow: /admin/\nDisallow: /dashboard/\nDisallow: /editor/\n", mimetype="text/plain")),
    
    # Frontend API
    # URL design as in: https://github.com/tinkerpop/rexster/wiki/Basic-REST-API
  
    # graph
    url(r'^api/graphs$','FuzzEd.api.graphs', name='graphs'),
    url(r'^api/graphs/(?P<graph_id>\d+)$', 'FuzzEd.api.graph', name='graph'),
    url(r'^api/graphs/(?P<graph_id>\d+)/transfers$', 'FuzzEd.api.graph_transfers', name='graph_transfers'),
    url(r'^api/graphs/(?P<graph_id>\d+)/graph_download$', 'FuzzEd.api_frontend.graph_download', name='frontend_graph_download'),

    # exports (graph downloads that return a job location instead of the direct result)
    url(r'^api/graphs/(?P<graph_id>\d+)/exports/pdf$', 
        'FuzzEd.api_frontend.job_create', {'job_kind': Job.PDF_RENDERING_JOB}, name='export_pdf'),
    url(r'^api/graphs/(?P<graph_id>\d+)/exports/eps$', 
        'FuzzEd.api_frontend.job_create', {'job_kind': Job.EPS_RENDERING_JOB}, name='export_eps'),

    # node
    url(r'^api/graphs/(?P<graph_id>\d+)/nodes$', 'FuzzEd.api.nodes', name='nodes'),
    url(r'^api/graphs/(?P<graph_id>\d+)/nodes/(?P<node_id>\d+)$', 'FuzzEd.api.node', name='node'),

    # properties
    url(r'^api/graphs/(?P<graph_id>\d+)/nodes/(?P<node_id>\d+)/properties$',
        'FuzzEd.api.properties', name='properties'),
    url(r'^api/graphs/(?P<graph_id>\d+)/nodes/(?P<node_id>\d+)/properties/(?P<key>)$',
        'FuzzEd.api.property', name='property'),

    # edges
    url(r'^api/graphs/(?P<graph_id>\d+)/edges$','FuzzEd.api.edges', name='edges'),
    url(r'^api/graphs/(?P<graph_id>\d+)/edges/(?P<edge_id>\d+)$','FuzzEd.api.edge', name='edge'),

    # undo/redo
    url(r'^api/graphs/(?P<graph_id>\d+)/redos$','FuzzEd.api.redos', name='redos'),
    url(r'^api/graphs/(?P<graph_id>\d+)/undos$','FuzzEd.api.undos', name='undos'),

    # analysis
    url(r'^api/graphs/(?P<graph_id>\d+)/analysis/cutsets$', 
        'FuzzEd.api_frontend.job_create', {'job_kind': Job.CUTSETS_JOB}, name='analyze_cutsets'),
    url(r'^api/graphs/(?P<graph_id>\d+)/analysis/topEventProbability$',
        'FuzzEd.api_frontend.job_create', {'job_kind': Job.TOP_EVENT_JOB}, name='analyze_top_event_probability'),

    # simulation
    url(r'^api/graphs/(?P<graph_id>\d+)/simulation/topEventProbability$',
        'FuzzEd.api_frontend.job_create', {'job_kind': Job.SIMULATION_JOB}, name='simulation_top_event_probability'),

    # jobs
    url(r'^api/jobs/(?P<job_id>\d+)$', 'FuzzEd.api_frontend.job_status', name='frontend_job_status'),
    url(r'^api/jobs/(?P<job_secret>\S+)/exitcode$', 'FuzzEd.api.job_exitcode', name='job_exitcode'),
    url(r'^api/jobs/(?P<job_secret>\S+)/files$', 'FuzzEd.api.job_files', name='job_files'),

    # user notifications
    url(r'^api/notifications/(?P<noti_id>\d+)/dismiss$','FuzzEd.api.noti_dismiss', name='noti_dismiss'),

    ## Application API
    ## All these calls are protected by OAuth, and not the session mechanisms
    url(r'^o/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    url(r'^api/graphs/(?P<graph_id>\d+)/pdf$', api_oauth.GraphPdfExportView.as_view()),
    url(r'^api/graphs/(?P<graph_id>\d+)/eps$', api_oauth.GraphEpsExportView.as_view()),
    url(r'^api/graphs/(?P<graph_id>\d+)/tex$', api_oauth.GraphTexExportView.as_view()),
    url(r'^api/graphs/(?P<graph_id>\d+)/graphml$', api_oauth.GraphGraphmlExportView.as_view()),
)
urlpatterns += staticfiles_urlpatterns()
